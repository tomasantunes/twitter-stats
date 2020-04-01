import tweepy
import json
import requests
import time
from datetime import datetime
from dateutil.parser import parse
import re
import random
import sqlite3
import sys
from flask import Flask, render_template

app = Flask(__name__)

with open('config.json', 'r') as config_file:
	config_data = json.load(config_file)
screen_name = config_data["auth"]["screen_name"]

auth = tweepy.OAuthHandler(config_data["auth"]["CONSUMER_KEY"], config_data["auth"]["CONSUMER_SECRET"])
auth.set_access_token(config_data["auth"]["ACCESS_TOKEN"], config_data["auth"]["ACCESS_SECRET"])
api = tweepy.API(auth)

@app.route('/')
def home():
	total_tweets = getTotalTweets()
	return render_template('index.html', total_tweets=total_tweets)
	
def getTotalTweets():
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()    
	cur.execute("SELECT COUNT(*) FROM tweets")
	count = cur.fetchone()
	return count[0]
	
def getTopTweets():
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()    
	cur.execute("SELECT * FROM tweets")
	rows = cur.fetchall()
	
	rows = sorted(rows, key=lambda x: x[5], reverse=True)
	
	with open('top_tweets.txt', 'w') as file:
		count = 0
		for row in rows:
			file.write("#" + str(count) + "\n")
			file.write("Author: "+row[1] + "\n")
			file.write("Tweet: "+ str(row[2].encode('utf-8')) + "\n")
			count += 1
		file.close()
	
def updateTweets():
	print("Starting")
	auth = tweepy.OAuthHandler(config_data["auth"]["CONSUMER_KEY"], config_data["auth"]["CONSUMER_SECRET"])
	auth.set_access_token(config_data["auth"]["ACCESS_TOKEN"], config_data["auth"]["ACCESS_SECRET"])
	api = tweepy.API(auth)
	
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()    
	cur.execute("SELECT * FROM tweets")
	rows = cur.fetchall()
	
	count = 0
	for row in rows:
		try:
			tweet = api.get_status(row[0])
			cur.execute("UPDATE tweets SET retweet_count = ?, favorite_count = ?", (tweet._json['retweet_count'], tweet._json['favorite_count']))
			con.commit()
			count += 1
			time.sleep(5)
			print(count)
		except tweepy.TweepError:
			print("TweepError")
		except tweepy.RateLimitError:
			print("RateLimitError")
			time.sleep(60*15)
			
	
	con.close()

def main():
	print("Starting")
	try:
		con = sqlite3.connect('tweets.db')
		cur = con.cursor()    
		cur.execute("CREATE TABLE IF NOT EXISTS tweets (tweet_id TEXT, screen_name TEXT, tweet TEXT, date TEXT, retweet_count INT, favorite_count INT)")
		con.commit()
		con.close()
	except sqlite3.Error as e:
		print("Error %s:", e.args[0])
		sys.exit(1)
	
	downloadTweets()
	timelines = loadTimelines()
	getActiveUsers(timelines)
	
def downloadTweets():
	print("Running.")
	count = 0
	try:
		users = tweepy.Cursor(api.followers, screen_name=screen_name).items()
		for user in users:
			getTimeline("@" + user._json['screen_name'])
			count += 1
			print(count)
			if (count > 4000):
				break
				
	except tweepy.TweepError:
		print("Tweep Error")
	print("Finished")
	
		
def loadTimelines():
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()    
	cur.execute("SELECT * FROM tweets")
	rows = cur.fetchall()
	
	timelines = {}
	for tweet in rows:
		screen_name = tweet[1]
		text = tweet[2]
		date = tweet[3]
		if (screen_name in timelines):
			timelines[screen_name]['tweets'].append({
				'tweet': text,
				'date': date
			})
		else:
			timelines[screen_name] = {'screen_name': screen_name, 'tweets': [{
				'tweet': text,
				'date': date
			}]}
			
	timelines2 = []
	for i in timelines:
		timelines2.append(timelines[i])
	return timelines2
		
def getHappyHour(dates):
	hours = {}
	for date in dates:
		date = parse(date)
		if date.hour in hours:
			hours[date.hour] += 1
		else:
			hours[date.hour] = 1
	return keywithmaxval(hours)
	
def getActiveUsers(timelines):
	days = {}
	for user in timelines:
		for tweet in user['tweets']:
			date = parse(tweet['date'])
			if date.day in days:
				days[date.day].append(user['screen_name'])
			elif date.day not in days and date.month == 6 and date.year == 2018:
				days[date.day] = [user['screen_name']]
	days_users = {}
	for day in days:
		days_users[day] = {}
		for user in days[day]:
			if user in days_users[day]:
				days_users[day][user] += 1
			else:
				days_users[day][user] = 1
	output_str = ""		
	for day in sorted(days_users.keys()):
		active_users = sortbyval(days_users[day])
		output_str += "Day " + str(day) + "\n"
		for user in active_users:
			output_str += user + "\n"
			
	with open('most_active.txt', 'w') as file:
		file.write(output_str)
		file.close()
		

def getBioKeywords(bios):
	words = {}
	for bio in bios:
		bio = re.sub(r"[^\w\s]", '', bio)
		bio_words = bio.split()
		for word in bio_words:
			if (word in words):
				words[word] += 1
			else:
				words[word] = 1
	words = sorted(words, key=words.get, reverse=True)

	with open('bio_keywords', 'w') as file:
		for word in words:
			file.write(word + "\n")
		file.close()
	

	

def getTimelineDates(screen_name):
	dates = []
	count = 0
	try:
		timeline = {'screen_name': screen_name, 'tweet_dates': []}
		for status in tweepy.Cursor(api.user_timeline, screen_name=screen_name).items():
			print(status._json)
			dates.append(status._json['created_at'])
			count += 1
			if (count > 25):
				break
		time.sleep(10)
	except tweepy.TweepError:
		print("TweepError")
	except tweepy.RateLimitError:
		print("RateLimitError")
		time.sleep(60*15)
	return dates
	
def getTimeline(screen_name):
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()
	timeline = {'screen_name': screen_name, 'tweets': []}
	count = 0
	try:
		
		for status in tweepy.Cursor(api.user_timeline, screen_name=screen_name).items():
			try:
				date = status._json['created_at']
				date = parse(date)
				if (date.day == 16 and date.month == 6 and date.year == 2018):
					cur.execute("SELECT * FROM tweets WHERE tweet_id = ?", (status._json['id'],))
					dups = cur.fetchall()
					if (len(dups) < 1):
						cur.execute("INSERT INTO tweets (tweet_id, screen_name, tweet, date, retweet_count, favorite_count) VALUES(?, ?, ?, ?, ?, ?)", (status._json['id'], screen_name, status._json['text'], status._json['created_at'], status._json['retweet_count'], status._json['favorite_count']))
						con.commit()
			except sqlite3.Error as e:
				print("Error %s:", e.args[0])
			count += 1
			if (count > 25):
				break
		time.sleep(5)
	except tweepy.TweepError:
		print("TweepError")
	except tweepy.RateLimitError:
		print("RateLimitError")
		time.sleep(60*15)
	con.close()
	return timeline
			
# function to handle errors
def error_handling(e):
	error = type(e)
	if error == tweepy.RateLimitError:
		print('Rate Limit Error')
	if error == tweepy.TweepError:
		print('Tweepy Error')

def keywithmaxval(d):
	v=list(d.values())
	k=list(d.keys())
	return k[v.index(max(v))]
	
def sortbyval(d):
	return sorted(d.keys(), key=d.__getitem__, reverse=True)
	
getActiveUsers(loadTimelines())
	
if __name__ == "__main__":
    app.run()
