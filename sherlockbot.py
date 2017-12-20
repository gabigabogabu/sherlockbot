import praw     # python reddit api wrapper
import datetime # account age etc
import logging  # logging
import re       # regex to extrect usernames
import prawcore # for exception handling
import requests # for exception handling
import urllib3  # for exception handling
from time import sleep  # retry throtteling
from threading import Thread    # multithreading
from praw.models import Comment # classify items as comment
from praw.models import Submission  # classify items as submission

__author__ = 'github.com/gaschu95'
__version__ = '0.0.1'

def get_logger():
    'returns a logger that writes to console and to file'
    log = logging.getLogger('_name_')
    logFormat = '[%(asctime)s] [%(threadName)s] [%(levelname)s] - %(message)s'

    # write to console
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(logFormat))
    log.addHandler(handler)

    # write to file
    handler = logging.FileHandler('sherlockbot.log')
    handler.setFormatter(logging.Formatter(logFormat))
    log.addHandler(handler)

    log.setLevel(level=logging.DEBUG)
    return log

def check_on_mention(reddit, log):
    'checks for new mentions and launches background checks'
    log.info('checking inbox')

    threads = []
    while True:
        try:
            # get mentions and iterate over them
            for item in reddit.inbox.stream():
                log.debug(str(item) + ' found')

                # get text of submission/comment
                text = ''
                if isinstance(item, Comment):
                    text = item.body
                if isinstance(item, Submission):
                    text = item.selftext

                # extract users to launch checks on
                users = []
                # find mentions in text
                e = re.compile("u/[-_0-9a-zA-Z]*")
                for m in e.finditer(text):
                    users.append(reddit.redditor(m.group()[2:]))

                # if noone mentioned check author and parent's author
                if not users:
                    if isinstance(item, Comment): users.append(item.parent().author)
                    users.append(item.author)

                # don't do checks on itself
                users.remove(reddit.user.me())
                # launch check for each mention
                for u in users:
                    t = Thread(target=background_check, args=(reddit, log, u, item), name=str(item)+'-Thread')
                    threads.append(t)
                    t.start()

                # mark as read, so it does not reappear after relaunches
                item.mark_read()

                # clean up
                threads = [t for t in threads if t.is_alive()]
        except (prawcore.exceptions.RequestException,
                requests.exceptions.ReadTimeout,
                urllib3.exceptions.ReadTimeoutError) as e:
                # Handle timeouts etc
            # log error
            logger.error(e)
            # sleep
            sleep(1)
            # repeat
            continue

def background_check(reddit, log, user, comment):
    'handle background check and posting'
    msg = do_background_check(reddit, log, user)
    post_results(reddit, log, comment, msg)

def comment_format(arg, line):
    return '{}:\t{}    \n'.format(arg, line)

def do_background_check(reddit, log, user):
    'does actual background check'
    log.info('doing background check for u/{}'.format(user.name))

    # config
    topCommentsInSubount = 5
    topCommentCount = 5

    # background check

    # basic info
    msg = 'u/{}    \n'.format(user.name)
    msg += comment_format('Link Karma', user.link_karma)
    msg += comment_format('Comment Karma', user.comment_karma)

    # account age
    account_created = datetime.datetime.fromtimestamp(user.created)
    account_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(user.created)
    msg += comment_format('account opened', str(account_created))
    msg += comment_format('account age', str(account_age))

    # users most frequent subreddits

    # process submissions
    submissionCount = 0 # how many submissions were made
    submissionsInSub = {} # subreddits and how many submissions were made
    submissionKarmaInSub = {} # subreddit and how much karma was earned
    for s in user.submissions.top(limit=None):
        submissionCount += 1
        if s.subreddit.display_name in submissionsInSub.keys():
            submissionsInSub[s.subreddit.display_name] += 1
        else:
            submissionsInSub[s.subreddit.display_name] = 1

        if s.subreddit.display_name in submissionKarmaInSub.keys():
            submissionKarmaInSub[s.subreddit.display_name] += s.score
        else:
            submissionKarmaInSub[s.subreddit.display_name] = s.score
    submissionKarmaInSub = dict([(s, submissionKarmaInSub[s]) for s in sorted(submissionKarmaInSub, key=submissionKarmaInSub.get, reverse=True)][:topCommentsInSubount])
    submissionsInSub = dict([(s, submissionsInSub[s]) for s in sorted(submissionsInSub, key=submissionsInSub.get, reverse=True)][:topCommentsInSubount])

    # process comments
    commentCount = 0 # how many comments were made
    CommentsInSub = {} # subreddits and how many comments were made
    CommentKarmaInSub = {} # subreddit and how much karma was earned
    for c in user.comments.top(limit=None):
        commentCount += 1
        if c.subreddit.display_name in CommentKarmaInSub.keys():
            CommentKarmaInSub[c.subreddit.display_name] += 1
        else:
            CommentKarmaInSub[c.subreddit.display_name] = 1

        if c.subreddit.display_name in CommentsInSub.keys():
            CommentsInSub[c.subreddit.display_name] += c.score
        else:
            CommentsInSub[c.subreddit.display_name] = c.score
    CommentKarmaInSub = dict([(s, CommentKarmaInSub[s]) for s in sorted(CommentKarmaInSub, key=CommentKarmaInSub.get, reverse=True)][:topCommentsInSubount])
    CommentsInSub = dict([(s, CommentsInSub[s]) for s in sorted(CommentsInSub, key=CommentsInSub.get, reverse=True)][:topCommentsInSubount])


    msg += comment_format('# of submissions:', submissionCount)
    msg += comment_format('most submission karma in', str(submissionKarmaInSub))
    msg += comment_format('most submissions in', str(submissionsInSub)
    msg += comment_format('# of comments', commentCount)
    msg += comment_format('most comment karma in', str(CommentKarmaInSub))
    msg += comment_format('most comments in', str(CommentsInSub))

    # TODO: get subreddit moderated by user
    # # moderator of
    # modSubs = []
    # for s in submissionsInSub:
    #     if user in reddit.subreddit(s).moderator():
    #         modSubs.append(reddit.subreddit(s))
    #
    # modSubs = modSubs
    # msg += 'moderates:\t{}    \n'.format(str(modSubs))

    # users top submissions as table
    msg += '\ntop submissions:    \n\n'
    msg += 'Sub|Points|text\n'
    msg += '--|--|--\n'
    for s in user.submissions.top(limit=topCommentCount):
        if s.selftext == '' or s.selftext == None:
            msg += s.subreddit.display_name + ' | ' + str(s.score) + ' | [' + s.title + '](' + s.url + ')\n'
        else:
            msg += s.subreddit.display_name + ' | ' + str(s.score) + ' | ' + s.selftext.replace('\n', ' ') + '\n'

    # users top comments as table
    msg += '\ntop comments:    \n\n'
    msg += 'Sub|Points|text\n'
    msg += '--|--|--\n'
    for c in user.comments.top(limit=topCommentCount):
        msg += c.subreddit.display_name + ' | ' + str(c.score) + ' | ' + c.body.replace('\n', ' ') + '\n'

    msg += '---\n^(I am a bot v{}. This message was created at {}.)'.format(__version__, str(datetime.datetime.now()))

    # ideas:
    # scan users comments for personal info
    # search for twitter user with same name
    # remember how often user was checked and also post that
    return msg

def post_results(reddit, log, comment, msg):
    'submit comment with background check results'
    log.info('replying results to comment {}'.format(str(comment)))
    comment.reply(msg)

def main():
    log = get_logger()
    log.info('logging in...')
    r = praw.Reddit('sherlockbot')
    mentionThread = Thread(target=check_on_mention, args=(r,log), name='mentionThread')
    mentionThread.start()
    # TODO: detect when to do checks on its own without being called

if __name__ == '__main__':
    main()
