# Notice of Upcoming Changes

## New and breaking changes coming on Oct. 15/16, 2021

I've (mostly) completed a major rewrite of this project, which you can peruse
in the [refactor](https://github.com/tobraha/dattoCheck/tree/refactor) branch of this
repository.

As I learn more and more about Python and object-oriented programming, this project
sort of keeps up with my very slow improvements.

While there are not too many functional changes with this rewrite,
one of the biggest changes is how the organization-specific data,
such as API keys and email addresses, are fed to the script.

If you're reading this, you are probably aware that the current implementation
uses quite a few command-line arguments to feed in this data. This is messy!
The reason for this is that I didn't want to have to hard-code any
of my org's private info (email address and API keys) into the script,
or to do so accidentally. Eventually, the number of command-line args
needed to run the script grew to an unpleasant amount.

Another problem I faced is that to introduce these upcoming changes,
it would be difficult to notify anyone who is actually using this
that they would need to update their script configurations if it was
set up the way I wrote in the instructions. I have no idea how many
people might be using this.


This led me to another concern - if someone set this up the way I wrote
in my instructions, they would have:

1. Cloned this repository to a Linux machine somewhere in their environment
2. Created a cron job that
    - runs a 'git pull' from the master branch of my repository
    - blindly runs 'main.py'; probably as root

It dawned on me that this is not terribly wise from a security perspective.
While you can _absolutely_ trust that I wouldn't introduce anything harmful (and
that my GitHub account is sufficiently secured against unwanted access
with MFA, strong password, all that fun stuff),
I am of mind that you absolutely _should not_ place that trust.

I will have some new recommendations on how you can fork this project to your own
GitHub account and then run it from there. If I make any changes, you can merge
them into your own fork after you have reviewed them.

# What is Actually Changing

So - now to the point!

The new changes eliminate almost all command line arguments in favor of a
configuration file for the script: 'config.py'. When you 'git pull' (or delete
and re-clone) these changes, you will have a file 'config-mk.py' that you will
need to copy to 'config.py'. Fill out this file with the specific info for your
organizaition. Here is what the relevant part of config-mk.py looks like:

```python

# API authentication
AUTH_USER = ''
AUTH_PASS = ''
AUTH_XML  = ''

# Email configs
EMAIL_FROM  = ''
EMAIL_TO    = []
EMAIL_CC    = []
EMAIL_LOGIN = EMAIL_FROM
EMAIL_PW    = ''
EMAIL_MX    = ''
EMAIL_PORT  = 25
EMAIL_SSL   = True
```

Pretty self-explanatory - just make sure that you keep the brackets for EMAIL_TO
and EMAIL_CC to maintain the format of a Python **_list_**.

If you just have one To/CC recipient, it should look like this:

```python
EMAIL_TO = ['someUser@example.com']
```

If you have two or more, then like this:

```python
EMAIL_TO = ['user1@example.com', 'user2@example.com', 'user3@example.com']
```

Now, the only command line arguments are:
- '-v' to enable verbose output. Use this if you are manually running the script
- '-u' to include unprotected volumes in the report (I use cron to include this once per week)

I will have have new setup instructions in the [README.md](https://github.com/tobraha/dattoCheck/blob/refactor/README.md)
file in the refactor branch where I'm working on this.

I plan on merging this rewrite into the master branch on October 16, 2021 at 0200 UTC.

As always, feel free to submit an issue here on GitHub if you have any problems.

<3 tobraha
