#!/usr/bin/env python3
#
#    Copyright (C) 2017 Simon Naunton
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import json
import keyring
from datetime import datetime, timedelta
from os import makedirs, remove
from os.path import getmtime, expanduser, exists
from requests import get
from requests.exceptions import RequestException
from sys import stderr, exit, argv
from time import sleep

def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)

def modification_date(filename):
    t = getmtime(filename)
    return datetime.fromtimestamp(t)

class iigenmon:
  __username = None
  __service = None
  __token = None
  __s_token = None
  __cache_dir = None
  __error = None
  __days_so_far = None
  __days_remaining = None
  __anytime_used = None
  __anytime_allocation = None
  __anytime_is_shaped = None
  __anytime_shaping_speed = None
  __uploads = None
  __freezone = None
  __retrieved = None
  __auth_error = False

  def __usage(self):
    u = "USAGE:\n" \
        "iigenmon.py username [service]\nRetrieves usage data for username, and optionally service, formated for XFCE4 genmon plugin.\n\n" \
        "iigenmon.py -p|--password username password\nSets the password that iigenmon.py will use for username when logging in to iinet.\n\n" \
        "iigenmon.py [-h|--help]\nShow this help text.\n"
    print(u)
    exit(0)

  def __setCacheDir(self):
    if(self.__cache_dir  == None):
      self.__cache_dir  = '%s/.cache/iigenmon.py' % expanduser("~")
      if not exists(self.__cache_dir ):
        makedirs(self.__cache_dir )

  def __getTokenFileName(self):
    return "%s/%s-tokens.json" % (self.__cache_dir ,self.__username)

  def __getUsageFileName(self):
    return "%s/%s-usage.json" % (self.__cache_dir ,self.__username)

  def __getNewTokenData(self):
    data = None
    try:
      password = keyring.get_password("iigenmon.py", self.__username)
      data = get("https://toolbox.iinet.net.au/cgi-bin/api.cgi?_USERNAME={}&_PASSWORD={}".format(self.__username, password), timeout=30).json()
      if(data):
        if(data["success"] == 1):
          with open(self.__getTokenFileName(), 'w') as outfile:
            json.dump(data, outfile)
        elif(data["error"] == "Invalid username or password"):
          self.__error = data["error"]
          self.__auth_error = True
          data = None
        else:
          self.__error = "ERROR: Error logging in to iinet: %s" % data["error"]
          data = None

    except RequestException as e:
      self.__error = "ERROR: Exception: %s" % e
      eprint(self.__error)

    return data

  def __getTokens(self):
    data = None
    self.__s_token = None
    self.__token = None

    try:
      data = json.load(open(self.__getTokenFileName()))
    except FileNotFoundError:
      data = self.__getNewTokenData()

    if(data):
      if(data["success"] == 1):
        services = None
        if(self.__service is None):
          services = [(s) for s in data["response"]["service_list"] if "Usage" in s["actions"]]
        else:
          services = [(s) for s in data["response"]["service_list"] if "Usage" in s["actions"] and self.__service == s["pk_v"]]

        if(services is None or len(services) <= 0):
          if(self.__service is None):
            self.__error = "Service not found"
          else:
            self.__error = "Service %s not found" % self.__service
        else:
          self.__service = services[0]["pk_v"]
          self.__s_token = services[0]["s_token"]
          self.__token = data["token"]
      else:
        self.__error = data["error"]

  def __getUsageData(self):
    data = None
    usageFileName = self.__getUsageFileName();
    if(self.__token and self.__s_token):
      try:
        data = get("https://toolbox.iinet.net.au/cgi-bin/api.cgi?Usage&_TOKEN={}&_SERVICE={}".format(self.__token, self.__s_token), timeout=30).json()
        if(data):
          if(data["success"] == 1):
            with open(usageFileName, 'w') as outfile:
              json.dump(data, outfile)
          elif(data["error"] == "Authentication required or token has expired"):
            # Only return false when tokens have expired
            return False
          else:
            self.__error = data["error"]
            data = None
      except RequestException as e:
        self.__error = "ERROR: Exception: %s" % e
        eprint(self.__error)

    if(data is None): # Load previous data
      try:
        data = json.load(open(usageFileName))
      except FileNotFoundError:
        e = "No cached data."
        if(self.__error):
          self.__error = "%s\n\n%s" % (self.__error,e)
        else:
          self.__error = e

    if(data is None):
      return False

    self.__days_so_far = int(data["response"]["quota_reset"]["days_so_far"])
    self.__days_remaining = int(data["response"]["quota_reset"]["days_remaining"])

    tt = data["response"]["usage"]["traffic_types"]
    self.__anytime_used = None
    self.__anytime_allocation = None
    at = [(t) for t in tt if t["classification"] == "anytime"]
    if(at):
      a = at[0]
      self.__anytime_used = int(a["used"])
      self.__anytime_allocation = int(a["allocation"])
      self.__anytime_is_shaped = False
      if(a["is_shaped"] == 1):
        self.__anytime_is_shaped = True
      self.__anytime_shaping_speed = a["shaping_speed"]

    self.__uploads = None
    up = [(t) for t in tt if t["classification"] == "uploads"]
    if(up):
      self.__uploads = int(up[0]["used"])

    self.__freezone = None
    fz = [(t) for t in tt if t["classification"] == "freezone"]
    if(fz):
      self.__freezone = int(fz[0]["used"])

    self.__retrieved = modification_date(usageFileName)

    return True

  def __display(self):
    anytime_used = None
    anytime_used_percent = None
    anytime_used_per_day = None
    anytime_remaining = None
    anytime_remaining_percent = None
    anytime_remaining_per_day = None
    anytime_allocation = None
    if(self.__anytime_used):
      anytime_used = round(self.__anytime_used / 1073741824 + 0.005,2)
      if(self.__days_so_far):
        anytime_used_per_day = round((self.__anytime_used / self.__days_so_far) / 1073741824 - 0.005,2)
      if(self.__anytime_allocation):
        anytime_used_percent = float((100.0 / self.__anytime_allocation) * self.__anytime_used)
        anytime_remaining = self.__anytime_allocation - self.__anytime_used
        anytime_remaining_percent = round((100.0 / self.__anytime_allocation) * anytime_remaining,2)
        anytime_remaining = round(anytime_remaining / 1073741824 - 0.005,2)
        anytime_allocation = round(self.__anytime_allocation / 1073741824 - 0.005,2)
        if(self.__days_remaining):
          anytime_remaining_per_day = round(((self.__anytime_allocation - self.__anytime_used) / self.__days_remaining) / 1073741824 - 0.005,2)
        if(self.__days_so_far):
          anytime_allocation_per_day = round((self.__anytime_allocation / (self.__days_remaining + self.__days_so_far - 1)) / 1073741824 - 0.005,2)

    uploads = None
    uploads_per_day = None
    if(self.__uploads):
      uploads = round(self.__uploads / 1073741824 + 0.005,2)
      if(self.__days_so_far):
        uploads_per_day = round((self.__uploads / self.__days_so_far) / 1073741824 - 0.005,2)

    freezone = None
    freezone_per_day = None
    if(self.__freezone):
      freezone = round(self.__freezone / 1073741824 + 0.005,2)
      if(self.__days_so_far):
        freezone_per_day = round((self.__freezone / self.__days_so_far) / 1073741824 - 0.005,2)

    if(self.__days_remaining):
      print("<txt>%02d </txt>" % self.__days_remaining)
    else:
      print("<txt>?? </txt>")

    if(anytime_remaining_percent):
      print("<bar>%f</bar>" % anytime_remaining_percent)
    else:
      print("<bar>0</bar>")

    print("<tool>")

    if(anytime_used):
      s = "Anytime Used: %.2fGiB" % anytime_used
      if(anytime_used_percent):
        s = "%s %.2f%%" % (s, anytime_used_percent)
      if(anytime_used_per_day):
        s = "%s %.2fGiB/day" % (s, anytime_used_per_day)
      print(s)

    if(anytime_remaining):
      s = "Anytime Remaining: %.2fGiB" % anytime_remaining
      if(anytime_remaining_percent):
        s = "%s %.2f%%" % (s, anytime_remaining_percent)
      if(anytime_remaining_per_day):
        s = "%s %.2fGiB/day" % (s, anytime_remaining_per_day)
      print(s)

    if(self.__anytime_is_shaped and self.__anytime_is_shaped == True):
      print("Currently Shaped to %s" % self.__anytime_shaping_speed)

    if(anytime_allocation):
      s = "Anytime Quota: %.2fGiB" % anytime_allocation
      if(anytime_allocation_per_day):
        s = "%s %.2fGiB/day" % (s, anytime_allocation_per_day)
      print(s)

    if(self.__uploads):
      s = "Uploads Used: %.2fGiB" % uploads
      if(uploads_per_day): 
        s = "%s %.2fGiB/day" % (s, uploads_per_day)
      print(s)

    if(self.__freezone):
      s = "Freezone Used: %.2fGiB" % freezone
      if(freezone_per_day):
        s = "%s %.2fGiB/day" % (s, freezone_per_day)
      print(s)

    if(self.__days_remaining):
      d = datetime.now() + timedelta(days=self.__days_remaining)
      print("Resets: %s (%d days)" % (d.strftime("%Y-%m-%d"), self.__days_remaining))

    if(self.__retrieved):
      print("Retrieved:", self.__retrieved.strftime("%Y-%m-%d %H:%M:%S"))

    if(self.__error):
      print("\nError: %s" % ' '.join(self.__error.split(None)))

    print("</tool>")

  def __set_password(self, password):
    keyring.set_password("iigenmon.py", self.__username, password)

  def __init__(self, argv):
    if(len(argv) <= 0 or argv[0] == "-h" or argv[0] == "--help"):
      self.__usage()

    if(argv[0] == '-p' or argv[0] == "--password"):
      if(len(argv) < 3):
        self.__usage()
      self.__username = argv[1]
      self.__set_password(argv[2])
      exit(0)

    self.__username = argv[0]
    if(len(argv) > 1):
      self.__service = argv[1]
    self.__setCacheDir()
    self.__getTokens()

    retries = 3
    tokenFileName = self.__getTokenFileName()
    while(retries > 0):
      if(self.__getUsageData() == False):
        # Refresh tokens
        if exists(tokenFileName):
          remove(tokenFileName)
        self.__getTokens()
        if(self.__auth_error):
          break
      else:
        break
      if(retries < 3): # do not wait if just refreshing tokens
        sleep(60)
      retries = retries - 1

    self.__display()

def main(args):
  iigenmon(args)

if __name__ == "__main__":
  main(argv[1:])
