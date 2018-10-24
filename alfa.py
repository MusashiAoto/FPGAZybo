#!/usr/bin/env python                                                                                                                                             
# -*- coding:utf-8 -*-                                                                                                                                            

from requests_oauthlib import OAuth1Session
import json
import sys
import time

    
### Constants                                                                                                                                                     
oath_key_dict = {
	"consumer_key": "lmwJUSjoiD6RaiPJm6MphUvMN",
	"consumer_secret": "UAyB8pVThUENxfcbWopOQWzEOyXtld0GFjweqMFpodbqykqT3G",
	"access_token": "554138197-RciGPN6MtDKQMEvZ1PYuzR281A8ZZ5Iy9IOkkiME",
	"access_token_secret": "xL7Qd8MH97FyeHYm4yHMFlngNStybAh7INDb1jGfiMoIx"
}


# -*- coding: utf-8 -*-
 
from requests_oauthlib import OAuth1Session
import json
import datetime, time, sys
from abc import ABCMeta, abstractmethod
 
date = datetime.datetime.now()

CK = 'lmwJUSjoiD6RaiPJm6MphUvMN'                             # Consumer Key
CS = 'UAyB8pVThUENxfcbWopOQWzEOyXtld0GFjweqMFpodbqykqT3G'    # Consumer Secret
AT = '554138197-RciGPN6MtDKQMEvZ1PYuzR281A8ZZ5Iy9IOkkiME'    # Access Token
AS = 'xL7Qd8MH97FyeHYm4yHMFlngNStybAh7INDb1jGfiMoIx'         # Accesss Token Secert
import csv # CSVファイルを扱うためのモジュールのインポート
import os


import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ['https://spreadsheets.google.com/feeds']


credentials = ServiceAccountCredentials.from_json_keyfile_name('My Project -f7b74b14e3c0.json', scope)


gc = gspread.authorize(credentials)


wks = gc.open_by_url('https://docs.google.com/spreadsheets/d/1LvkQK8ndXtg5FTgy2d_N3TZQA24iCIFCrrdqH6KYx34/edit#gid=2010821734')

#wks = gc.open_by_url('https://docs.google.com/spreadsheets/d/1WnkA259NLQrEcIcMR8XnJPtXqeiTvfgfz34oSVZF6Pc/edit#gid=0')




class TweetsGetter(object):
	__metaclass__ = ABCMeta
 
	def __init__(self):
		self.session = OAuth1Session(CK, CS, AT, AS)
 
	@abstractmethod
	def specifyUrlAndParams(self, keyword):
		'''
		呼出し先 URL、パラメータを返す
		'''
 
	@abstractmethod
	def pickupTweet(self, res_text, includeRetweet):
		'''
		res_text からツイートを取り出し、配列にセットして返却
		'''
 
	@abstractmethod
	def getLimitContext(self, res_text):
		'''
		回数制限の情報を取得 （起動時）
		'''
 
	def collect(self, total = -1, onlyText = False, includeRetweet = False):
		'''
		ツイート取得を開始する
		'''
 
		#----------------
		# 回数制限を確認
		#----------------
		self.checkLimit()
 
		#----------------
		# URL、パラメータ
		#----------------
		url, params = self.specifyUrlAndParams()
		params['include_rts'] = str(includeRetweet).lower()
		# include_rts は statuses/user_timeline のパラメータ。search/tweets には無効
 
		#----------------
		# ツイート取得
		#----------------
		cnt = 0
		unavailableCnt = 0
		while True:
			res = self.session.get(url, params = params)
			if res.status_code == 503:
				# 503 : Service Unavailable
				if unavailableCnt > 10:
					raise Exception('Twitter API error %d' % res.status_code)
 
				unavailableCnt += 1
				print ('Service Unavailable 503')
				self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
				continue
 
			unavailableCnt = 0
 
			if res.status_code != 200:
				raise Exception('Twitter API error %d' % res.status_code)
 
			tweets = self.pickupTweet(json.loads(res.text))
			if len(tweets) == 0:
				# len(tweets) != params['count'] としたいが
				# count は最大値らしいので判定に使えない。
				# ⇒  "== 0" にする
				# https://dev.twitter.com/discussions/7513
				break
 
			for tweet in tweets:
				if (('retweeted_status' in tweet) and (includeRetweet is False)):
					pass
				else:
					if onlyText is True:
						yield tweet['text']
					else:
						yield tweet
 
					cnt += 1
					if cnt % 100 == 0:
						print ('%d件 ' % cnt)
 
					if total > 0 and cnt >= total:
						return
 
			params['max_id'] = tweet['id'] - 1
 
			# ヘッダ確認 （回数制限）
			# X-Rate-Limit-Remaining が入ってないことが稀にあるのでチェック
			if ('X-Rate-Limit-Remaining' in res.headers and 'X-Rate-Limit-Reset' in res.headers):
				if (int(res.headers['X-Rate-Limit-Remaining']) == 0):
					self.waitUntilReset(int(res.headers['X-Rate-Limit-Reset']))
					self.checkLimit()
			else:
				print ('not found  -  X-Rate-Limit-Remaining or X-Rate-Limit-Reset')
				self.checkLimit()
 
	def checkLimit(self):
		'''
		回数制限を問合せ、アクセス可能になるまで wait する
		'''
		unavailableCnt = 0
		while True:
			url = "https://api.twitter.com/1.1/application/rate_limit_status.json"
			res = self.session.get(url)
 
			if res.status_code == 503:
				# 503 : Service Unavailable
				if unavailableCnt > 10:
					raise Exception('Twitter API error %d' % res.status_code)
 
				unavailableCnt += 1
				print ('Service Unavailable 503')
				self.waitUntilReset(time.mktime(datetime.datetime.now().timetuple()) + 30)
				continue
 
			unavailableCnt = 0
 
			if res.status_code != 200:
				raise Exception('Twitter API error %d' % res.status_code)
 
			remaining, reset = self.getLimitContext(json.loads(res.text))
			if (remaining == 0):
				self.waitUntilReset(reset)
			else:
				break
 
	def waitUntilReset(self, reset):
		'''
		reset 時刻まで sleep
		'''
		seconds = reset - time.mktime(datetime.datetime.now().timetuple())
		seconds = max(seconds, 0)
		print ('\n     =====================')
		print ('     == waiting %d sec ==' % seconds)
		print ('     =====================')
		sys.stdout.flush()
		time.sleep(seconds + 10)  # 念のため + 10 秒
 
	@staticmethod
	def bySearch(keyword):
		return TweetsGetterBySearch(keyword)
 
	@staticmethod
	def byUser(screen_name):
		return TweetsGetterByUser(screen_name)
 
 
class TweetsGetterBySearch(TweetsGetter):
	'''
	キーワードでツイートを検索
	'''
	def __init__(self, keyword):
		super(TweetsGetterBySearch, self).__init__()
		self.keyword = keyword
        
	def specifyUrlAndParams(self):
		'''
		呼出し先 URL、パラメータを返す
		'''
		url = 'https://api.twitter.com/1.1/search/tweets.json'
		params = {'q':self.keyword, 'count':100}
		return url, params
 
	def pickupTweet(self, res_text):
		'''
		res_text からツイートを取り出し、配列にセットして返却
		'''
		results = []
		for tweet in res_text['statuses']:
			results.append(tweet)
 
		return results
 
	def getLimitContext(self, res_text):
		'''
		回数制限の情報を取得 （起動時）
		'''
		remaining = res_text['resources']['search']['/search/tweets']['remaining']
		reset     = res_text['resources']['search']['/search/tweets']['reset']
 
		return int(remaining), int(reset)
    
 
class TweetsGetterByUser(TweetsGetter):
	'''
	ユーザーを指定してツイートを取得
	'''
	def __init__(self, screen_name):
		super(TweetsGetterByUser, self).__init__()
		self.screen_name = screen_name
        
	def specifyUrlAndParams(self):
		'''
		呼出し先 URL、パラメータを返す
		'''
		url = 'https://api.twitter.com/1.1/statuses/user_timeline.json'
		params = {'screen_name':self.screen_name, 'count':200}
		return url, params
 
	def pickupTweet(self, res_text):
		'''
		res_text からツイートを取り出し、配列にセットして返却
		'''
		results = []
		for tweet in res_text:
			results.append(tweet)
 
		return results
 
	def getLimitContext(self, res_text):
		'''
		回数制限の情報を取得 （起動時）
		'''
		remaining = res_text['resources']['statuses']['/statuses/user_timeline']['remaining']
		reset     = res_text['resources']['statuses']['/statuses/user_timeline']['reset']
 
		return int(remaining), int(reset)
 
 
if __name__ == '__main__':
 
	# キーワードで取得
	getter = TweetsGetter.bySearch(u'archeage'or'Archeage'or'アーキエイジ'or'ArcheAge'or'#ArcheAgeJP')
    
	# ユーザーを指定して取得 （screen_name）
	#getter = TweetsGetter.byUser('AbeShinzo')
 
	cnt = 0
	dd =[]

	sheet = wks.worksheet("sheet1")
	#sheet.update_cell(1, 1, 'hoge')
	last=sheet.row_count

	gscount=0
	values_list = sheet.col_values(1)
	multi_array = [[0 for column in range(30)] for row in range(100)]

	for i in values_list:

		gscount+=1

	rowscount = sheet.row_values(gscount)
	print("実行")
	from datetime import datetime,timedelta,timezone
	import pytz
	JST = timezone(timedelta(hours=+9),"JST")
	now= datetime.now(JST)
	for tweet in getter.collect(total = 3000):
		shl=[]

		dd =[]
		coh='{}'.format(tweet['created_at']).astimezone(JST)
		dd =list(coh)
		if dd[0]==rowscount[0] and dd[1]==rowscount[1] and dd[2]==rowscount[2] and dd[4]==rowscount[4] and dd[5]==rowscount[5] and dd[6]==rowscount[6] and dd[8]==rowscount[8]and dd[11]==rowscount[11] and dd[12]==rowscount[12] and dd[13]==rowscount[13] and dd[14]==rowscount[14] and dd[15]==rowscount[15]and dd[16]==rowscount[16] and dd[17]==rowscount[17] and dd[18]==rowscount[18]:
			break
		else:
			for ves in range (30):
			 multi_array[cnt][ves]=dd[ves]

           
		cnt=cnt+1

 
    
	print(cnt)
	coon=cnt
	pcin=0
	if cnt>=1:
		for vehemos in range(gscount+1,gscount+1+cnt):
			for kamisama in range(30):
				atanaso=multi_array[coon-1][kamisama]
			
				if kamisama != 20:
					sheet.update_cell(vehemos,kamisama+1,atanaso)
			coon=coon-1 
			if pcin == 2:
				break
			pcin+=1 

