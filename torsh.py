#! /bin/env python

from __future__ import unicode_literals, print_function

import cmd
import getopt
import socket
import sys
import getpass

from pytorctl import TorCtl

import formatter

class TorSH(cmd.Cmd):
  """ Shell for talking to Tor and debugging """
  def __init__(self):
    self.localenv = {}
    self.prompt = "torsh # "
    self.completekey = "\t"
    self.cmdqueue = []
    self.stdout = sys.stdout

    self._socket = None
    self._connection = None
    self._threads = None

    self._do_aliases()

  def do_EOF(self, line):
    if self._connection:
      self._connection.close()
    
    return True

  def do_connect(self, data):
    """ 
    Connects to a Tor instance by ControlSocket or ControlPort.

    Usage:
      connect --method=port --host=<host> --port=<port number> --pass=<passphrase>
      or
      connect --method=socket --path=<socket_path>
    """

    controlport = True
    host = "localhost"
    port = 9051
    passphrase = None
    path = None

    try:
      opts, args = getopt.getopt(data.split(" "), "m:", \
          ["method=", "host=", "port=", "pass=",\
           "path="])

      for opt, arg in opts:
        if opt == "--method":
          if arg == "port":
            controlport = True
          elif arg == "socket":
            controlport = False
          else:
            raise Exception("Unkown method for connection. \
                Use sock for ControlSocket and port for ControlPort")
        elif opt == "--host":
          host = arg
        elif opt == "--port":
          port = int(arg)
        elif opt == "--pass":
          passphrase = arg
        elif opt == "--path":
          path = arg

      if not controlport:
        raise Exception("ControlSocket connection isn't supported yet, \
            use ControlPort instead.")

      self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self._socket.connect((host,port))
      self._connection = TorCtl.Connection(self._socket)
      self._threads = self._connection.launch_thread()
      auth_type, auth_value = self._connection.get_auth_type(), ""
      
      if auth_type == TorCtl.AUTH_TYPE.PASSWORD:
        if passphrase: auth_value = passphrase
        else:
          try: auth_value = getpass.getpass()
          except KeyboardInterrupt: return None
      elif auth_type == AUTH_TYPE.COOKIE:
        auth_value = self._connection.get_auth_cookie_path()

      self._connection.authenticate(auth_value)

      self.prompt = "torsh@%s:%i # " % (host, port)

    except getopt.GetoptError:
      # TODO: implement a generic usage function
      # self.usage() 
      print("ERROR at the arguments")
      return
    except Exception as e:
      print("ERROR:", e[0])

  def do_get_info(self, name):
    """
    Issues a GET-INFO command with the first element of name.
    If name has more than one word, it's ignored.

    Usage:
      get-info network-status
      get-info addr-mappings/all
    """

    try:
      output = self._connection.get_info(name.split(" ")[:1])
      for line in formatter.select_formatter(name, output[name]):
        print(line)
    except Exception as e:
      print("ERROR:", e[0])

  def do_set_options(self, keyvalues):
    """
      Issues a SETCONF command.

      Usage:
        set_options key1=val1 key2=val2 ...
    """

    keyvalue_list = keyvalues.split(" ")
    final_list = []
    for keyvalue in keyvalue_list:
      pair = keyvalue.split("=")
      final_list.append((pair[0], pair[1]))

    try:
      output = self._connection.set_options(final_list)
      print(formatter.format_reply(output[0]))
    except Exception as e:
      print(e[0])

  def do_reset_options(self, keys):
    """
      Issues a RESETCONF for the given keys.

      Usage:
        reset_conf key1 key2
    """

    try:
      output = self._connection.reset_options(keys.split(" "))
      print(formatter.format_reply(output[0]))
    except Exception as e:
      print(e[0])

  def do_get_option(self, name):
    """
      Issues a GETCONF.

      Usage:
        get_option key1 key2 ...
    """

    try:
      output = self._connection.get_option(name)
      formatted = formatter.format_getconf(output)
      for line in formatted:
        print(line)
    except Exception as e:
      print(e[0])

  def _do_aliases(self):
    self.do_conn = self.do_connect
    self.do_gi = self.do_get_info
    self.do_so = self.do_set_options
    self.do_ro = self.do_reset_options

if __name__ == '__main__':
    TorSH().cmdloop()
