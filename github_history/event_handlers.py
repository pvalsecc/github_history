import github
import re


# noinspection PyPep8Naming
def IssueCommentEvent(repo, event):
    issue = _issue_common(repo, event)
    issue.setdefault('events', []).append({
        'when': event.created_at,
        'what': 'comment ' + event.payload['action']
    })


# noinspection PyPep8Naming
def IssuesEvent(repo, event):
    issue = _issue_common(repo, event)
    issue.setdefault('events', []).append({
        'when': event.created_at,
        'what': 'Issue ' + event.payload['action']
    })


# noinspection PyPep8Naming
def GollumEvent(repo, event):
    wiki = repo['wiki']
    for page_event in event.payload['pages']:
        page = wiki.setdefault(page_event['page_name'], {})
        if 'title' not in page:
            page['title'] = page_event['title']
        page.setdefault('events', []).append({
            'when': event.created_at,
            'what': page_event['action']
        })


# noinspection PyPep8Naming
def PullRequestReviewCommentEvent(repo, event):
    branch = _pr_common(repo, event)
    branch.setdefault('events', []).append({
        'when': event.created_at,
        'what': 'PR comment ' + event.payload['action']
    })


# noinspection PyPep8Naming
def PullRequestEvent(repo, event):
    branch = _pr_common(repo, event)
    what = 'PR ' + event.payload['action']
    pr = event.payload['pull_request']
    if event.payload['action'] == 'closed':
        if pr['merged']:
            what += ' merged'
        else:
            what += ' dropped'
    branch.setdefault('events', []).append({
        'when': event.created_at,
        'what': what
    })
    # _get_jira(repo['branches'], pr['head']['ref'], pr['title'])
    _get_jira(repo['branches'], pr['head']['ref'], pr['body'])


# noinspection PyPep8Naming
def PushEvent(repo, event):
    branches = repo['branches']
    commits = event.payload['commits']
    if len(commits) > 0 and not commits[-1]['message'].startswith('Merge pull request #'):
        ref = event.payload['ref'].replace('refs/heads/', '')
        branches.setdefault(ref, {}).setdefault('events', []).append({
            'when': event.created_at,
            'what': 'push: %s' % ('; '.join(_get_commit_titles(event.payload['commits'])))
        })
        for commit in commits:
            _get_jira(branches, ref, commit['message'])


# noinspection PyPep8Naming
def CreateEvent(repo, event):
    branches = repo['branches']
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


# noinspection PyPep8Naming
def DeleteEvent(repo, event):
    ref_type = event.payload['ref_type']
    if ref_type == 'branch':
        branches = repo['branches']
        branch = branches.setdefault(event.payload['ref'], {})
        branch.setdefault('events', []).append({
            'when': event.created_at,
            'what': 'deleted'
        })
    else:
        print("UNKNOWN DeleteEvent ref_type: " + ref_type)


# noinspection PyPep8Naming
def ForkEvent(repo, event):
    pass


# noinspection PyPep8Naming
def MemberEvent(repo, event):
    pass


# noinspection PyPep8Naming
def CommitCommentEvent(repo, event):
    pass


# noinspection PyPep8Naming
def WatchEvent(repo, event):
    pass


def _get_commit_title(commit):
    message = commit['message']
    return message.split('\n')[0]


def _get_commit_titles(commits):
    return map(_get_commit_title, commits)


PR_CACHE = {}


def _get_pr(repo, id_):
    global PR_CACHE
    if id_ in PR_CACHE:
        return PR_CACHE[id_]

    try:
        result = repo.get_pull(id_)
    except github.UnknownObjectException:
        result = None  # not a PR

    PR_CACHE[id_] = result
    return result


def _pr_common(repo, event):
    branches = repo['branches']
    pr = event.payload['pull_request']
    branch = branches.setdefault(pr['head']['ref'], {})
    if 'title' not in branch:
        branch['title'] = pr['title']
    if 'pr_number' not in branch:
        branch['pr_number'] = pr['number']
    return branch


def _issue_common(repo, event):
    issues = repo['issues']
    id_ = event.payload['issue']['number']
    issue = issues.setdefault(id_, {})
    if 'title' not in issue:
        issue['title'] = event.payload['issue']['title']
    pr = _get_pr(event.repo, id_)
    if pr is not None:
        branch = repo['branches'].setdefault(pr.head.ref, {'events': []})
        if branch is not None:
            if 'pr_number' not in branch:
                branch['pr_number'] = id_
            if 'title' not in branch:
                branch['title'] = pr.title
    return issue


JIRA_RE = re.compile(r'\b([A-Z\d]+-\d+)\b')


def _get_jira(branches, ref, message):
    if message is not None:
        jira_matcher = JIRA_RE.search(message)
        if jira_matcher is not None:
            branches[ref].setdefault('jira', set()).add(jira_matcher.group(1))
