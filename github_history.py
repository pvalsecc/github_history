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


def print_events(events):
    for event in sorted(events, key=lambda x: x['when'].timestamp()):
        print('        %s: %s' % (event['when'].strftime("%a %d/%m %H:%M"), event['what']))


def get_commit_title(commit):
    message = commit['message']
    return message.split('\n')[0]


def get_commit_titles(commits):
    return map(get_commit_title, commits)


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
    parser.add_argument('--user', help='GitHub username to fetch to history for',
                        **default_from_config(config, 'user', 'user'))
    parser.add_argument('--token', help='GitHub API token to use',
                        **default_from_config(config, 'user', 'token'))

    parser.add_argument('--days', help='number of days to fetch', type=int, default=7)

    return parser.parse_args()


def main():
    args = parse_args()
    logging.basicConfig(level=logging.INFO)

    iface = github.Github(args.token, per_page=100, timeout=30)
    user = iface.get_user(args.user)
    older_time = datetime.datetime.fromtimestamp(time.time() - 3600 * 24 * args.days)

    repos = fetch_report(older_time, user)
    print_report(repos)

    print("\nRemaining API calls: %d/%d" % iface.rate_limiting)


def fetch_report(older_time, user):
    repos = {}
    for event in user.get_events():
        if event.created_at < older_time:
            break
        if event.type in {'DeleteEvent', 'ForkEvent'}:
            continue

        root_repo = get_root_repo(event.repo)
        if root_repo is None:
            continue
        repo_name = root_repo.full_name

        repo = repos.setdefault(repo_name, {'branches': {}, 'issues': {}, 'wiki': {}})
        branches = repo['branches']
        issues = repo['issues']
        wiki = repo['wiki']

        if event.type == 'CreateEvent':
            ref_type = event.payload['ref_type']
            if ref_type == 'branch':
                branches.setdefault(event.payload['ref'], {}).setdefault('events', []).append({
                    'when': event.created_at,
                    'what': 'branch created'
                })

            elif ref_type == 'tag':
                branches.setdefault(event.payload['ref'], {}).setdefault('events', []).append({
                    'when': event.created_at,
                    'what': 'tag created'
                })
            elif ref_type == 'repository':
                pass
            else:
                print("UNKNOWN CreateEvent ref_type: " + ref_type)

        elif event.type == 'PushEvent':
            if event.payload['commits'][-1]['message'].startswith('Merge pull request #'):
                continue
            ref = event.payload['ref'].replace('refs/heads/', '')
            branches.setdefault(ref, {}).setdefault('events', []).append({
                'when': event.created_at,
                'what': 'push: %s' % ('; '.join(get_commit_titles(event.payload['commits'])))
            })

        elif event.type == 'PullRequestEvent':
            pr = event.payload['pull_request']
            branch = branches.setdefault(pr['head']['ref'], {})
            if 'title' not in branch:
                branch['title'] = pr['title']
            if 'pr_number' not in branch:
                branch['pr_number'] = event.payload['number']
            what = 'PR ' + event.payload['action']
            if event.payload['action'] == 'closed':
                if event.payload['pull_request']['merged']:
                    what += ' merged'
                else:
                    what += ' dropped'
            branch.setdefault('events', []).append({
                'when': event.created_at,
                'what': what
            })

        elif event.type == 'PullRequestReviewCommentEvent':
            pr = event.payload['pull_request']
            branch = branches.setdefault(pr['head']['ref'], {})
            if 'title' not in branch:
                branch['title'] = pr['title']
            if 'pr_number' not in branch:
                branch['pr_number'] = pr['number']
            branch.setdefault('events', []).append({
                'when': event.created_at,
                'what': 'PR comment ' + event.payload['action']
            })

        elif event.type == 'IssuesEvent':
            issue = issues.setdefault(event.payload['issue']['number'], {})
            if 'title' not in issue:
                issue['title'] = event.payload['issue']['title']
            issue.setdefault('events', []).append({
                'when': event.created_at,
                'what': 'Issue ' + event.payload['action']
            })

        elif event.type == 'GollumEvent':
            for page_event in event.payload['pages']:
                page = wiki.setdefault(page_event['page_name'], {})
                if 'title' not in page:
                    page['title'] = page_event['title']
                page.setdefault('events', []).append({
                    'when': event.created_at,
                    'what': page_event['action']
                })

        elif event.type == 'IssueCommentEvent':
            issue = issues.setdefault(event.payload['issue']['number'], {})
            if 'title' not in issue:
                issue['title'] = event.payload['issue']['title']
            issue.setdefault('events', []).append({
                'when': event.created_at,
                'what': 'comment ' + event.payload['action']
            })

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
            print('    %s%s%s: %s%s%s' % (fg('light_green') + attr('bold'), branch_name, attr(0),
                                          fg('green'), branch.get('title', ''), attr(0)))
            print_events(branch['events'])

        for issue_id, issue in sorted(issues.items()):
            print('    %s#%s%s: %s%s%s' % (fg('light_green') + attr('bold'), issue_id, attr(0),
                                           fg('green'), issue.get('title', ''), attr(0)))
            print_events(issue['events'])

        for page_name, page in sorted(wiki.items()):
            print('    %s[%s]%s: %s%s%s' % (fg('light_green') + attr('bold'), page_name, attr(0),
                                            fg('green'), page.get('title', ''), attr(0)))
            print_events(page['events'])


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
