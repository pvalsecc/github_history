# GitHub history fetcher

Use the GitHub API to retrace the activity of a user.

The information can be given in a INI file located in `~/.config/github_history.ini` looking like that:

```ini
[user]
user=pvalsecc
token=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Those values can also be passed as parameters.

The token must be generated from the [GitHub developer settings](https://github.com/settings/tokens) and
must have those permissions: `read:user, repo`.

To run it, use the `github_history` wrapper script. It will setup a virtualenv for you.
