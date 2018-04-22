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
	'''returns a logger that writes to console and to file'''
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
	'''checks for new mentions and launches background checks'''
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
					users.append(item.author)
					if isinstance(item, Comment): users.append(item.parent().author)

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
	'''handle background check and posting'''
	msg = do_background_check(reddit, log, user)
	post_results(reddit, log, comment, msg)

def comment_format(arg, line):
	return '{}:\t{}    \n'.format(arg, line)

def do_background_check(reddit, log, user):
	'''does actual background check'''
	log.info('doing background check for u/{}'.format(user.name))

	# config
	topcomments_in_subount = 5
	topCommentCount = 5

	# background check

	# basic info
	msg = comment_format('Username', user.name)
	msg += comment_format('Link Karma', user.link_karma)
	msg += comment_format('Comment Karma', user.comment_karma)

	# account age
	account_created = datetime.datetime.fromtimestamp(user.created)
	account_age = datetime.datetime.now() - datetime.datetime.fromtimestamp(user.created)
	msg += comment_format('account opened', str(account_created))
	msg += comment_format('account age', str(account_age))

	# users most frequent subreddits

	# process submissions
	submission_count = 0 # how many submissions were made
	submissions_in_sub = {} # subreddits and how many submissions were made
	submission_karma_in_sub = {} # subreddit and how much karma was earned
	for s in user.submissions.top(limit=None):
		submission_count += 1
		if s.subreddit.display_name in submissions_in_sub.keys():
			submissions_in_sub[s.subreddit.display_name] += 1
		else:
			submissions_in_sub[s.subreddit.display_name] = 1

		if s.subreddit.display_name in submission_karma_in_sub.keys():
			submission_karma_in_sub[s.subreddit.display_name] += s.score
		else:
			submission_karma_in_sub[s.subreddit.display_name] = s.score
	avgSubmissionKarma = 0
	if submission_count > 0:
		avgSubmissionKarma = user.link_karma / submission_count
	submission_karma_in_sub = dict([(s, submission_karma_in_sub[s]) for s in sorted(submission_karma_in_sub, key=submission_karma_in_sub.get, reverse=True)][:topcomments_in_subount])
	submissions_in_sub = dict([(s, submissions_in_sub[s]) for s in sorted(submissions_in_sub, key=submissions_in_sub.get, reverse=True)][:topcomments_in_subount])
	# averageSubmission_karma_in_sub = {k: submission_karma_in_sub[k]/submissions_in_sub[k] for k in submission_karma_in_sub}

	# process comments
	comment_count = 0 # how many comments were made
	comments_in_sub = {} # subreddits and how many comments were made
	comment_karma_in_sub = {} # subreddit and how much karma was earned
	for c in user.comments.top(limit=None):
		comment_count += 1
		if c.subreddit.display_name in comment_karma_in_sub.keys():
			comment_karma_in_sub[c.subreddit.display_name] += 1
		else:
			comment_karma_in_sub[c.subreddit.display_name] = 1

		if c.subreddit.display_name in comments_in_sub.keys():
			comments_in_sub[c.subreddit.display_name] += c.score
		else:
			comments_in_sub[c.subreddit.display_name] = c.score
	avgCommentKarma = 0
	if comment_count > 0:
		avgCommentKarma = user.comment_karma / comment_count
	comment_karma_in_sub = dict([(s, comment_karma_in_sub[s]) for s in sorted(comment_karma_in_sub, key=comment_karma_in_sub.get, reverse=True)][:topcomments_in_subount])
	comments_in_sub = dict([(s, comments_in_sub[s]) for s in sorted(comments_in_sub, key=comments_in_sub.get, reverse=True)][:topcomments_in_subount])

	# add to message
	msg += comment_format('No. of submissions:', submission_count)
	msg += comment_format('average submission Karma', avgSubmissionKarma)
	msg += comment_format('most submission karma in', str(submission_karma_in_sub))
	msg += comment_format('most submissions in', str(submissions_in_sub))
	msg += comment_format('No. of comments', comment_count)
	msg += comment_format('average comment Karma', avgCommentKarma)
	msg += comment_format('most comment karma in', str(comment_karma_in_sub))
	msg += comment_format('most comments in', str(comments_in_sub))

	# TODO: get subreddit moderated by user

	#
	# # WARNING: TAKES FOR EVER TO RUN
	#

	# # moderator of
	# modSubs = []
	# for s in submissions_in_sub:
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
	'''submit comment with background check results'''
	log.info('replying results to comment {}'.format(str(comment)))
	comment.reply(msg)

def main():
	log = get_logger()
	log.info('logging in...')
	reddit = praw.Reddit('sherlockbot')
	mentionThread = Thread(target=check_on_mention, args=(reddit,log), name='mentionThread')
	mentionThread.start()
	# do_background_check(reddit, log, reddit.redditor('sherlockbot'))
	# TODO: detect when to do checks on its own without being called

if __name__ == '__main__':
	main()
