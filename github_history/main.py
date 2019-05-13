"""
Fetch the given user's history from github
"""

import argparse
from colored import fg, attr
import configparser
import datetime
import github
import logging
import os
import time


from github_history import event_handlers


def print_events(events):
    for event in sorted(events, key=lambda x: x['when'].timestamp()):
        print('        %s: %s' % (event['when'].strftime("%a %d/%m %H:%M"), event['what']))


def default_from_config(config, section, name):
    if section in config:
        sec = config[section]
        if name in sec:
            return {'default': sec[name]}
    return {'required': True}


def parse_args():
    config = configparser.ConfigParser()
    config.read(os.path.join(os.path.expanduser('~'), '.config', 'github_history.ini'))

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', help='GitHub username to fetch the history for',
                        **default_from_config(config, 'user', 'user'))
    parser.add_argument('--token', help='GitHub API token to use',
                        **default_from_config(config, 'user', 'token'))

    parser.add_argument('--days', help='number of days to fetch', type=int, default=8)

    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO)

    iface = github.Github(args.token, per_page=100, timeout=30)
    user = iface.get_user(args.user)
    older_time = datetime.datetime.fromtimestamp(time.time() - 3600 * 24 * args.days)

    repos = fetch_report(older_time, user)
    print_report(repos)

    print(fg('grey_69') + ("Remaining API calls: %d/%d" % iface.rate_limiting) + attr(0))


def fetch_report(older_time, user):
    repos = {}
    for event in user.get_events():
        if event.created_at < older_time:
            break

        root_repo = get_root_repo(event.repo)
        if root_repo is None:
            continue
        repo_name = root_repo.full_name

        repo = repos.setdefault(repo_name, {'branches': {}, 'issues': {}, 'wiki': {}})

        if hasattr(event_handlers, event.type):
            getattr(event_handlers, event.type)(repo, event)
        else:
            print('UNKNOWN event: when=%s type=%s repo=%s' % (event.created_at, event.type, repo_name))
    return repos


def print_report(repos):
    for repo_name, repo in sorted(repos.items()):
        # merge issue events into branches if the issue is actually a PR for that branch
        branches = repo['branches']
        issues = repo['issues']
        wiki = repo['wiki']
        merge_prs_in_branches(branches, issues)

        if len(branches) + len(issues) + len(wiki) == 0:
            continue

        print("%s%s ---------------%s" % (fg('light_red') + attr('bold'), repo_name, attr(0)))

        for branch_name, branch in sorted(branches.items()):
            print('    %s%s%s: %s%s%s %s%s%s' % (fg('light_green') + attr('bold'), branch_name, attr(0),
                                                 fg('green'), branch.get('title', ''), attr(0),
                                                 fg('blue'), ', '.join(branch.get('jira', [])), attr(0)))
            print_events(branch['events'])

        for issue_id, issue in sorted(issues.items()):
            print('    %s#%s%s: %s%s%s' % (fg('light_green') + attr('bold'), issue_id, attr(0),
                                           fg('green'), issue.get('title', ''), attr(0)))
            print_events(issue['events'])

        for page_name, page in sorted(wiki.items()):
            print('    %s[%s]%s: %s%s%s' % (fg('light_green') + attr('bold'), page_name, attr(0),
                                            fg('green'), page.get('title', ''), attr(0)))
            print_events(page['events'])
        print()


def merge_prs_in_branches(branches, issues):
    for branch_name, branch in sorted(branches.items()):
        if branch_name.startswith('requires-io-'):
            del branches[branch_name]
        if branch.get('pr_number') in issues:
            branch['events'] += issues[branch['pr_number']]['events']
            del issues[branch['pr_number']]


ROOT_REPO_CACHE = {}


def get_root_repo(repo):
    global ROOT_REPO_CACHE
    id_ = repo.id
    if id_ in ROOT_REPO_CACHE:
        return ROOT_REPO_CACHE[id_]

    try:
        if not repo.fork:
            result = repo
        else:
            result = get_root_repo(repo.parent)
    except github.GithubException:
        print("ERROR fetching info about " + repo.name)
        result = None

    ROOT_REPO_CACHE[id_] = result
    return result


main()
