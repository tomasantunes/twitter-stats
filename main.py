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
	users = getUsers() 
	total_users = len(users)
	return render_template('index.html', total_tweets=total_tweets, total_users=total_users)

@app.route('/bios-keywords')
def biosKeywords():
	users = getUsers()
	bios_keywords = getBioKeywords(getUserBios(users))
	return render_template('bios-keywords.html', bios_keywords=bios_keywords)

@app.route('/search-bios')
def searchBiosRoute():
	query = request.args.get('query')
	results = searchBios(query)
	n_results = len(results)
	return render_template('search-bios.html', results=results, n_results=n_results)

@app.route('/most-active')
def mostActive():
	timelines = loadTimelines()
	most_active = getActiveUsers(timelines)
	print(most_active)
	return render_template('most-active.html', most_active=most_active)
	
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
		cur.execute("CREATE TABLE IF NOT EXISTS users (user_id TEXT, screen_name TEXT, n_tweets INT, n_followers INT, n_following INT)")
		con.commit()
		con.close()
	except sqlite3.Error as e:
		print("Error %s:", e.args[0])
		sys.exit(1)

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
	print(timelines2)
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
			elif date.day not in days:
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
	most_active_users = []
	c = 0
	for day in sorted(days_users.keys()):
		active_users = sortbyval(days_users[day])
		output_str += "Day " + str(day) + "\n"
		most_active_users.append({"day": "Day " + str(day), "users": []})
		for user in active_users:
			output_str += user + "\n"
			most_active_users[c]["users"].append(user)
		c += 1
			
	with open('most_active.txt', 'w') as file:
		file.write(output_str)
		file.close()

	return most_active_users

def getUsers():
	target = "@" + screen_name
	print("Processing target: " + target)

	filename = target + "_follower_ids.json"
	follower_ids = try_load_or_process(filename, get_follower_ids, target)

	filename = target + "_followers.json"
	user_objects = try_load_or_process(filename, get_user_objects, follower_ids)
	return user_objects

def getUserBios(users):
	bios = []
	for user in users:
		bios.append(user['description'])
	return bios		

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
	listofTuples = sorted(words.items(), reverse=True, key=lambda x: x[1])

	with open('bio_keywords', 'w') as file:
		for elem in listofTuples:
			file.write(str(elem[1]) + " - " + str(elem[0].encode("utf-8")) + "\n")
		file.close()

	return listofTuples

def searchBios(query):
	users = getUsers()

	results = []
	for user in users:
		bio = user['description']
		bio = re.sub(r"[^\w\s]", '', bio)
		bio_words = bio.split()
		for word in bio_words:
			if (word.lower() == query.lower()):
				results.append(user['name'] + ": " + bio)

	return results
			
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
	
# Helper functions to load and save intermediate steps
def save_json(variable, filename):
    with io.open(filename, "w", encoding="utf-8") as f:
        f.write(str(json.dumps(variable, indent=4, ensure_ascii=False)))

def load_json(filename):
    ret = None
    if os.path.exists(filename):
        try:
            with io.open(filename, "r", encoding="utf-8") as f:
                ret = json.load(f)
        except:
            pass
    return ret

def try_load_or_process(filename, processor_fn, function_arg):
    load_fn = None
    save_fn = None
    if filename.endswith("json"):
        load_fn = load_json
        save_fn = save_json
    else:
        load_fn = load_bin
        save_fn = save_bin
    if os.path.exists(filename):
        print("Loading " + filename)
        return load_fn(filename)
    else:
        ret = processor_fn(function_arg)
        print("Saving " + filename)
        save_fn(ret, filename)
        return ret

# Some helper functions to convert between different time formats and perform date calculations
def twitter_time_to_object(time_string):
    twitter_format = "%a %b %d %H:%M:%S %Y"
    match_expression = "^(.+)\s(\+[0-9][0-9][0-9][0-9])\s([0-9][0-9][0-9][0-9])$"
    match = re.search(match_expression, time_string)
    if match is not None:
        first_bit = match.group(1)
        second_bit = match.group(2)
        last_bit = match.group(3)
        new_string = first_bit + " " + last_bit
        date_object = datetime.strptime(new_string, twitter_format)
        return date_object

def time_object_to_unix(time_object):
    return int(time_object.strftime("%S"))

def twitter_time_to_unix(time_string):
    return time_object_to_unix(twitter_time_to_object(time_string))

def seconds_since_twitter_time(time_string):
    input_time_unix = int(twitter_time_to_unix(time_string))
    current_time_unix = int(get_utc_unix_time())
    return current_time_unix - input_time_unix

def get_utc_unix_time():
    dts = datetime.utcnow()
    return time.mktime(dts.timetuple())

# Get a list of follower ids for the target account
def get_follower_ids(target):
    return api.followers_ids(target)

# Twitter API allows us to batch query 100 accounts at a time
# So we'll create batches of 100 follower ids and gather Twitter User objects for each batch
def get_user_objects(follower_ids):
    batch_len = 100
    num_batches = len(follower_ids) / 100
    batches = (follower_ids[i:i+batch_len] for i in range(0, len(follower_ids), batch_len))
    all_data = []
    for batch_count, batch in enumerate(batches):
        sys.stdout.write("\r")
        sys.stdout.flush()
        sys.stdout.write("Fetching batch: " + str(batch_count) + "/" + str(num_batches))
        sys.stdout.flush()
        users_list = api.lookup_users(user_ids=batch)
        users_json = (map(lambda t: t._json, users_list))
        all_data += users_json
    return all_data

# Creates one week length ranges and finds items that fit into those range boundaries
def make_ranges(user_data, num_ranges=20):
    range_max = 604800 * num_ranges
    range_step = range_max/num_ranges

# We create ranges and labels first and then iterate these when going through the whole list
# of user data, to speed things up
    ranges = {}
    labels = {}
    for x in range(num_ranges):
        start_range = x * range_step
        end_range = x * range_step + range_step
        label = "%02d" % x + " - " + "%02d" % (x+1) + " weeks"
        labels[label] = []
        ranges[label] = {}
        ranges[label]["start"] = start_range
        ranges[label]["end"] = end_range
    for user in user_data:
        if "created_at" in user:
            account_age = seconds_since_twitter_time(user["created_at"])
            for label, timestamps in ranges.items():
                if account_age > timestamps["start"] and account_age < timestamps["end"]:
                    entry = {} 
                    id_str = user["id_str"] 
                    entry[id_str] = {} 
                    fields = ["screen_name", "name", "created_at", "friends_count", "followers_count", "favourites_count", "statuses_count"] 
                    for f in fields: 
                        if f in user: 
                            entry[id_str][f] = user[f] 
                    labels[label].append(entry) 
    return labels
    
def usersReport():
	target = "@" + screen_name
	print("Processing target: " + target)

# Get a list of Twitter ids for followers of target account and save it
	filename = target + "_follower_ids.json"
	follower_ids = try_load_or_process(filename, get_follower_ids, target)

# Fetch Twitter User objects from each Twitter id found and save the data
	filename = target + "_followers.json"
	user_objects = try_load_or_process(filename, get_user_objects, follower_ids)
	total_objects = len(user_objects)

# Record a few details about each account that falls between specified age ranges
	ranges = make_ranges(user_objects)
	filename = target + "_ranges.json"
	save_json(ranges, filename)

# Print a few summaries
	print
	print("\t\tFollower age ranges")
	print("\t\t===================")
	total = 0
	following_counter = Counter()
	for label, entries in sorted(ranges.items()):
		print("\t\t" + str(len(entries)) + " accounts were created within " + label)
		total += len(entries)
		for entry in entries:
			for id_str, values in entry.items():
				if "friends_count" in values:
					following_counter[values["friends_count"]] += 1
	print("\t\tTotal: " + str(total) + "/" + str(total_objects))
	print
	print("\t\tMost common friends counts")
	print("\t\t==========================")
	total = 0
	for num, count in following_counter.most_common(20):
		total += count
		print("\t\t" + str(count) + " accounts are following " + str(num) + " accounts")
	print("\t\tTotal: " + str(total) + "/" + str(total_objects))
	print
	print

main()
	
if __name__ == "__main__":
    app.run()
