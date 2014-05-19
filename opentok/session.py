class Session(object):
    """
    Represents an OpenTok session.

    Use the OpenTok.createSession() method to create an OpenTok session. Use the
    session_id property of the Session object to get the session ID.

    @attr_reader [String] session_id The session ID.
    @attr_reader [String] api_secret @private The OpenTok API secret.
    @attr_reader [String] api_key @private The OpenTok API key.
    @attr_reader [Boolean] p2p Set to true if the session's streams will be transmitted directly
      between peers; set to false if the session's streams will be transmitted using the OpenTok
      media server. See the OpenTok.createSession() method.
    @attr_reader [String] location The location hint IP address. See the OpenTok.createSession()
      method.
    """
    def __init__(self, sdk, session_id, **kwargs):
        self.session_id = session_id
        self.sdk = sdk
        for key, value in kwargs.items():
            setattr(self, key, value)

    def generate_token(self, **kwargs):
        """
          Generates a token for the session.

          :param String role: The role for the token. Valid values are defined in the Role
          class:

          * `Roles.subscriber` -- A subscriber can only subscribe to streams.

          * `Roles.publisher` -- A publisher can publish streams, subscribe to
            streams, and signal. (This is the default value if you do not specify a role.)

          * `Roles.moderator` -- In addition to the privileges granted to a
            publisher, in clients using the OpenTok.js 2.2 library, a moderator can call the
            `forceUnpublish()` and `forceDisconnect()` method of the
            Session object.

          :param int expire_time: The expiration time of the token, in seconds since the UNIX epoch.
          The maximum expiration time is 30 days after the creation time. The default expiration
          time is 24 hours after the token creation time.

          :param String data: A string containing connection metadata describing the
          end-user. For example, you can pass the user ID, name, or other data describing the
          end-user. The length of the string is limited to 1000 characters. This data cannot be
          updated once it is set.

          :rtype:
          The token string.
        """
        return self.sdk.generate_token(self.session_id, **kwargs)