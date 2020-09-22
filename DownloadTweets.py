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
from flask import Flask, render_template, request
from collections import Counter
from datetime import datetime, date, time, timedelta
import sys
import json
import os
import io
import re
import time

with open('config.json', 'r') as config_file:
	config_data = json.load(config_file)
screen_name = config_data["auth"]["screen_name"]

auth = tweepy.OAuthHandler(config_data["auth"]["CONSUMER_KEY"], config_data["auth"]["CONSUMER_SECRET"])
auth.set_access_token(config_data["auth"]["ACCESS_TOKEN"], config_data["auth"]["ACCESS_SECRET"])
api = tweepy.API(auth)

def main():
	print("Starting")
	try:
		con = sqlite3.connect('tweets.db')
		cur = con.cursor()    
		cur.execute("CREATE TABLE IF NOT EXISTS tweets (tweet_id TEXT, screen_name TEXT, tweet TEXT, date TEXT, retweet_count INT, favorite_count INT)")
		con.commit()
		cur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT, screen_name TEXT, n_tweets INT, n_followers INT, n_following INT)")
		con.commit()
		con.close()
	except sqlite3.Error as e:
		print("Error %s:", e.args[0])
		sys.exit(1)

def getTimeline(screen_name, fetch_date):
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()
	timeline = {'screen_name': screen_name, 'tweets': []}
	count = 0
	try:
		
		for status in tweepy.Cursor(api.user_timeline, screen_name=screen_name).items():
			try:
				date = status._json['created_at']
				date = parse(date)
				if (date.day == fetch_date[0] and date.month == fetch_date[1] and date.year == fetch_date[2]):
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
		#time.sleep(5)
	except tweepy.TweepError:
		print("TweepError")
	except tweepy.RateLimitError:
		print("RateLimitError")
		time.sleep(60*15)
	con.close()
	return timeline

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

	
def downloadTweets(fetch_date):
	print("Running.")
	count = 0
	try:
		users = tweepy.Cursor(api.followers, screen_name=screen_name).items()
		for user in users:
			getTimeline("@" + user._json['screen_name'], fetch_date)
			count += 1
			print(count)
			if (count > 100):
				break
				
	except tweepy.TweepError:
		print("Tweep Error")
	print("Finished")

def downloadTweets2():
	print("Running.")
	con = sqlite3.connect('tweets.db')
	cur = con.cursor()
	count = 0
	max_tweets = 100
	try:
		for status in tweepy.Cursor(api.home_timeline).items(max_tweets):
			try:
				date = status._json['created_at']
				date = parse(date)
				if (date.day == fetch_date[0] and date.month == fetch_date[1] and date.year == fetch_date[2]):
					cur.execute("SELECT * FROM tweets WHERE tweet_id = ?", (status._json['id'],))
					dups = cur.fetchall()
					if (len(dups) < 1):
						cur.execute("INSERT INTO tweets (tweet_id, screen_name, tweet, date, retweet_count, favorite_count) VALUES(?, ?, ?, ?, ?, ?)", (status._json['id'], status._json['user']['screen_name'], status._json['text'], status._json['created_at'], status._json['retweet_count'], status._json['favorite_count']))
						con.commit()
			except sqlite3.Error as e:
				print("Error %s:", e.args[0])
			count += 1
			print(count)
		#time.sleep(5)
	except tweepy.TweepError:
		print("TweepError")
	except tweepy.RateLimitError:
		print("RateLimitError")
		time.sleep(60*15)
	con.close()
	print("Downloaded " + str(count) + " tweets.")
	print("Finished")

fetch_date = [22, 9, 2020]
main()
downloadTweets2()
