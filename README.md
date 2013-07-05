This is a python script that scans a server for sites that need Drupal updates, and creates a task in Active Collab for each update required.

*The first time you run the script you should run it with the -h or --help option.*

# Requirements

* Drush
* Python (at least version 2.7)
* Python "Requests" library

# Configuration

The first time you run the script it'll create a blank configuration file. You will be instructed to edit this file. Once you've done that you can use the script without much effort.

# Cronjobs
One of the main reasons to use a script like this is to have automatic, daily update checks for all sites on a server.

*Before using this script via a cronjob, please run it first manually (as the same user who will own the cronjob) to configure it and make sure it'll do what you expect!*

*If you're running the script from a cronjob, make sure that Drush is somewhere in the cron user's $PATH.*

Here's an example cronjob (all on a single line):

* It runs every day at 02:15
* The Drupal sites are located up to one level below /webapps/
(e.g., _/webapps/*/httpdocs_)

<code>15  2   *   *   *   /usr/local/bin/python2.7 /usr/local/bin/drupal-update-tasker.py</code>
