#!/usr/bin/env python
import sys
import os
import subprocess
import glob
import requests
import logging
from ConfigParser import SafeConfigParser

LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

# File logging
#fh = logging.FileHandler("result.log")
#fh.setLevel(logging.DEBUG)
#fh.setFormatter(formatter)
#LOG.addHandler(fh)

# Console logging
ch = logging.StreamHandler()
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
LOG.addHandler(ch)


def write_blank_config():
    try:
        with open(configfile_path, 'w') as configfile:
            configfile.write("[system_settings]")
            configfile.write("\n\n# REQUIRED: Which directory contains your Drupal sites (you can optionally traverse deeper from this root directory using the traverse_depth setting below)\n# Example: scan_directory = /var/www/")
            configfile.write("\nscan_directory = ")
            configfile.write("\n\n# REQUIRED: How many levels deep to look for Drupal site files.\n# Use traverse_depth = 0 here if sites lived at /var/www/mysite1/index.php and /var/www/mysite2/index.php.\n# Use traverse_depth = 1 if sites lived at /var/www/mysite1/httpdocs/index.php and /var/www/mysite2/httpdocs/index.php")
            configfile.write("\ntraverse_depth = 0")
            configfile.write("\n\n# REQUIRED: The system name will be appended to the beginning of the task name.\n# Example: system_name = web122")
            configfile.write("\nsystem_name = ")
            configfile.write("\n\n\n[active_collab_settings]")
            configfile.write("\n\n# REQUIRED: Your Active Collab API URL.\n# Example: api_url = http://www.ac-projects.com")
            configfile.write("\napi_url = ")
            configfile.write("\n\n# REQUIRED: Your Active Collab API user token.\n# Example: api_token = 8-349W6U6lsl8W8heJ9We0h3h3BSyoS7n3KJtisotL")
            configfile.write("\napi_token = ")
            configfile.write("\n\n# REQUIRED: The project ID under which the tasks will be created.\n# Get this from the projects table in the database.\n# Example: project_id = 349")
            configfile.write("\nproject_id = ")
            configfile.write("\n\n# OPTIONAL: The milestone ID under which the tasks will be created.\n# Get this from the project_objects table in the database.\n# Example: milestone_id = 1123")
            configfile.write("\nmilestone_id = ")
            configfile.write("\n\n# OPTIONAL: The category ID under which the tasks will be created.\n# Get this from the categories table in the database.\n# Example: category_id = 1820")
            configfile.write("\ncategory_id = ")
    except IOError:
        LOG.error('Could not create template config file.')
        sys.exit()


def process_config(configfile_path):
    global scandir
    global traverse
    global system_name
    global collab_api_token
    global collab_api_url
    global collab_project_id
    global collab_milestone_id
    global collab_category_id

    parser = SafeConfigParser()
    parser.read(configfile_path)

    scandir = parser.get('system_settings', 'scan_directory')
    traverse = parser.get('system_settings', 'traverse_depth')
    system_name = parser.get('system_settings', 'system_name')
    collab_api_url = parser.get('active_collab_settings', 'api_url')
    collab_api_token = parser.get('active_collab_settings', 'api_token')
    collab_project_id = parser.get('active_collab_settings', 'project_id')
    collab_milestone_id = parser.get('active_collab_settings', 'milestone_id')
    collab_category_id = parser.get('active_collab_settings', 'category_id')

configfile_path = os.path.join(os.path.expanduser('~'), '.drupal_update_tasker')
try:
    with open(configfile_path) as configfile:
        # The file exists, so process it (note that we're passing the path, not the file object)
        process_config(configfile_path)
except IOError:
    write_blank_config()
    LOG.error('No config file found. Created a blank config file. Please edit %s and try again.' % configfile_path)
    sys.exit()

if not scandir or not traverse or not system_name or not collab_api_url or not collab_api_token or not collab_project_id:
    LOG.error('Missing required settings. Please edit %s and try again.' % configfile_path)
    sys.exit()


# Emulate the which binary
# http://stackoverflow.com/a/377028
def which(program):
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

# Look for Drush and store its location; quit if we cannot find it
drush_app = which('drush')
if drush_app == None:
    sys.exit("ERROR: Could not find the Drush application in $PATH. If you are \
running this from a cronjob, try setting cron's PATH to include the drush \
application.")


def make_get_request(path_info, parameters=None):
    if parameters is None:
        parameters = {}
    parameters['auth_api_token'] = collab_api_token
    parameters['format'] = 'json'
    parameters['path_info'] = path_info
    r = requests.get(collab_api_url, params=parameters, verify=False)
    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return False


def make_post_request(path_info, data_payload, parameters=None):
    if parameters is None:
        parameters = {}
    parameters['auth_api_token'] = collab_api_token
    parameters['format'] = 'json'
    parameters['path_info'] = path_info
    r = requests.post(collab_api_url, params=parameters, data=data_payload, verify=False)
    if r.status_code == requests.codes.ok:
        return r.json()
    else:
        return False


def project_tasks():
    # Returns open and closed tasks that are not archived
    result = make_get_request('projects/' + str(collab_project_id) + '/tasks')
    all_tasks = dict()
    if result:
        for task in result:
            # Use the task_id (relative to the project), not the id (database unique task ID)
            all_tasks[task['task_id']] = {'name': task['name'], 'milestone_id': task['milestone_id']}
    return all_tasks


def find_task_by_name(search_name, tasks):
    for task_id, task in tasks.items():
        if search_name.lower() == task['name'].lower():
            # We have a match on name only
            # If we're checking within a specific milestone, make sure we're limiting to only this milestone
            if collab_milestone_id:
                if collab_milestone_id == task['milestone_id']:
                    return task_id
            else:
                return task_id
    return 0


def create_task(task_name, attributes):
    #valid_keys = ['name', 'body', 'visibility', 'category_id', 'label_id',
    #              'milestone_id', 'priority', 'assignee_id', 'other_assignees', 'due_on']
    data = dict()
    data['submitted'] = 'submitted'
    data['task[name]'] = task_name
    data['task[priority]'] = 0
    data['task[label_id]'] = 0
    if collab_milestone_id:
        data['task[milestone_id]'] = collab_milestone_id
    if collab_category_id:
        data['task[category_id]'] = collab_category_id
    for key, val in attributes.items():
        data['task[' + key + ']'] = val
    result = make_post_request('projects/%s/tasks/add' % collab_project_id, data)
    return result


# Process a Drupal directory (dir MUST be a Drupal directory
# as we're not checking this here!)
def process_dir(directory):
    os.chdir(directory)
    LOG.info('Checking "%s" for updates...' % directory)
    drush = subprocess.Popen([drush_app, 'pm-update', '--pipe', '--simulate',
                             '--security-only'], stdout=subprocess.PIPE)
    results = drush.stdout.read()
    if results:
        lines = results.split("\n")
        for line in lines:
            if len(line) > 5:
                task_name = system_name + ' ' + directory + ' ' + line.replace('SECURITY-UPDATE-available', '')
                task_id = find_task_by_name(task_name, tasks)
                if not task_id:
                    attributes = {}
                    created_task = create_task(task_name, attributes)
                    if created_task:
                        task_id = created_task['task_id']
                        LOG.info('Task doesn\'t exist; created new task #%d "%s"' % (task_id, task_name))
                    else:
                        LOG.error('Task doesn\'t exist and could not create task "%s"' % task_name)
                else:
                    LOG.info('Task already exists (#%d) "%s"' % (task_id, task_name))

    os.chdir(scandir)

# Clean up the paths to fix any problems we might
# have with user paths (--dir=~/xyz won't work otherwise)
scandir = os.path.expanduser(scandir)
if not os.path.exists(scandir):
    sys.exit("ERROR: Could not find the scan directory.")

# Move to the directory that contains the Drupal sites
os.chdir(scandir)

# Get all tasks from this project (to quickly check later if task exists)
tasks = project_tasks()
if not tasks:
    sys.exit("ERROR: Could not connect to Active Collab and/or get list of tasks within project specified.")

# Traverse into subdirectories until the --traverse depth is reached
count = 0
while count < int(traverse) + 1:
    count += 1
    wildcards = '*/' * count
    for name in glob.glob(wildcards + 'sites/all/modules'):
        process_dir(name.replace('/sites/all/modules', ''))

LOG.info('Finished checking sites for required updates.')
sys.exit()
