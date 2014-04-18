"""
OpenTok Python Library v0.91.0
http://www.tokbox.com/

Copyright 2011, TokBox, Inc.
"""

__version__ = '2.0.0-beta'


import urllib
import datetime
import calendar
import time
import hmac
import hashlib
import base64
import random
import requests
import json


dthandler = lambda obj: obj.isoformat() if isinstance(obj, datetime.datetime)  or isinstance(obj, datetime.date) else None


class OpenTokException(Exception):
    """Generic OpenTok Error. All other errors extend this."""
    pass


class RequestError(OpenTokException):
    """Indicates an error during the request. Most likely an error connecting
    to the OpenTok API servers. (HTTP 500 error).
    """
    pass


class AuthError(OpenTokException):
    """Indicates that the problem was likely with credentials. Check your API
    key and API secret and try again.
    """
    pass


class NotFoundError(OpenTokException):
    """Indicates that the element requested was not found.  Check the parameters
    of the request.
    """
    pass


class ArchiveError(OpenTokException):
    """Indicates that there was a archive specific problem, probably the status
    of the requested archive is invalid.
    """
    pass


class SessionProperties(object):
    echoSuppression_enabled = None
    multiplexer_numOutputStreams = None
    multiplexer_switchType = None
    multiplexer_switchTimeout = None
    p2p_preference = "p2p.preference"

    def __iter__(self):
        d = {
            'echoSuppression.enabled': self.echoSuppression_enabled,
            'multiplexer.numOutputStreams': self.multiplexer_numOutputStreams,
            'multiplexer.switchType': self.multiplexer_switchType,
            'multiplexer.switchTimeout': self.multiplexer_switchTimeout,
            'p2p.preference': self.p2p_preference,
        }
        return d.iteritems()


class RoleConstants:
    """List of valid roles for a token."""
    SUBSCRIBER = 'subscriber'  # Can only subscribe
    PUBLISHER = 'publisher'    # Can publish, subscribe, and signal
    MODERATOR = 'moderator'    # Can do the above along with forceDisconnect and forceUnpublish


class OpenTokSession(object):

    def __init__(self, session_id):
        self.session_id = session_id


class OpenTokArchive(object):

    def __init__(self, sdk, values):
        self.sdk = sdk
        self.id = values.get('id')
        self.name = values.get('name')
        self.status = values.get('status')
        self.session_id = values.get('sessionId')
        self.partner_id = values.get('partnerId')
        self.created_at = datetime.datetime.fromtimestamp(values.get('createdAt') / 1000)
        self.size = values.get('size')
        self.duration = values.get('duration')
        self.url = values.get('url')

    def stop(self):
        self.sdk.stop_archive(self.id)

    def delete(self):
        self.sdk.delete_archive(self.id)

    def attrs(self):
        return dict((k, v) for k, v in self.__dict__.iteritems() if k is not "sdk")

    def json(self):
        return json.dumps(self.attrs(), default=dthandler, indent=4)


class OpenTokArchiveList(object):

    def __init__(self, values):
        self.count = values.get('count')
        self.items = map(lambda x: OpenTokArchive(self, x), values.get('items', []))

    def __iter__(self):
        for x in self.items:
            yield x

    def attrs(self):
        return {
            'count': self.count,
            'items': map(OpenTokArchive.attrs, self.items)
        }

    def json(self):
        return json.dumps(self.attrs(), default=dthandler, indent=4)


class OpenTokSDK(object):
    """Use this SDK to create tokens and interface with the server-side portion
    of the Opentok API.
    """
    TOKEN_SENTINEL = 'T1=='
    API_URL = 'https://api.opentok.com'

    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret.strip()

    def generate_token(self, session_id, role=None, expire_time=None, connection_data=None, **kwargs):
        """
        Generate a token which is passed to the JS API to enable widgets to connect to the Opentok api.
        session_id: Specify a session_id to make this token only valid for that session_id.
        role: One of the constants defined in RoleConstants. Default is publisher, look in the documentation to learn more about roles.
        expire_time: Integer timestamp. You can override the default token expire time of 24h by choosing an explicit expire time. Can be up to 7d after create_time.
        """
        create_time = datetime.datetime.utcnow()
        if not session_id:
            raise OpenTokException('Null or empty session ID are not valid')
        sub_session_id = session_id[2:]
        decoded_session_id = ""
        for i in range(0, 3):
            new_session_id = sub_session_id+("="*i)
            new_session_id = new_session_id.replace("-", "+").replace("_", "/")
            try:
                decoded_session_id = base64.b64decode(new_session_id)
                if "~" in decoded_session_id:
                    break
            except TypeError:
                pass
        try:
            if decoded_session_id.split('~')[1] != str(self.api_key):
                raise OpenTokException("An invalid session ID was passed")
        except Exception:
            raise OpenTokException("An invalid session ID was passed")

        if not role:
            role = RoleConstants.PUBLISHER

        if role != RoleConstants.SUBSCRIBER and \
                role != RoleConstants.PUBLISHER and \
                role != RoleConstants.MODERATOR:
            raise OpenTokException('%s is not a valid role' % role)

        data_params = dict(
            session_id=session_id,
            create_time=calendar.timegm(create_time.timetuple()),
            role=role,
        )
        if expire_time is not None:
            if isinstance(expire_time, datetime.datetime):
                data_params['expire_time'] = calendar.timegm(expire_time.timetuple())
            else:
                try:
                    data_params['expire_time'] = int(expire_time)
                except (ValueError, TypeError):
                    raise OpenTokException('Expire time must be a number')

            if data_params['expire_time'] < time.time():
                raise OpenTokException('Expire time must be in the future')

            if data_params['expire_time'] > time.time() + 2592000:
                raise OpenTokException('Expire time must be in the next 30 days')

        if connection_data is not None:
            if len(connection_data) > 1000:
                raise OpenTokException('Connection data must be less than 1000 characters')
            data_params['connection_data'] = connection_data

        data_params['nonce'] = random.randint(0,999999)
        data_string = urllib.urlencode(data_params, True)

        sig = self._sign_string(data_string, self.api_secret)
        token_string = '%s%s' % (self.TOKEN_SENTINEL, base64.b64encode('partner_id=%s&sig=%s:%s' % (self.api_key, sig, data_string)))
        return token_string

    def create_session(self, location='', properties={}, **kwargs):
        """Create a new session in the OpenTok API. Returns an OpenTokSession
        object with a session_id property. location: IP address of the user
        requesting the session. This is used for geolocation to choose which
        datacenter the session will live on. properties: An instance of the
        SessionProperties object. Fill in the fields that you are interested in
        to use features of the groups API. Look in the documentation for more
        details. Also accepts any dict-like object.
        """
        #ip_passthru is a deprecated argument and has been replaced with location
        if 'ip_passthru' in kwargs:
            location = kwargs['ip_passthru']
        params = dict(api_key=self.api_key)
        params['location'] = location
        params.update(properties)

        try:
            response = requests.post(self.session_url(), data=params, headers=self.headers())

            if response.status_code == 403:
                raise AuthError('Failed to create session, invalid credentials')
            if not response.content:
                raise RequestError()
            import xml.dom.minidom as xmldom
            dom = xmldom.parseString(response.content)
        except Exception, e:
            raise RequestError('Failed to create session: %s' % str(e))

        try:
            error = dom.getElementsByTagName('error')
            if error:
                error = error[0]
                raise AuthError('Failed to create session (code=%s): %s' % (error.attributes['code'].value, error.firstChild.attributes['message'].value))

            session_id = dom.getElementsByTagName('session_id')[0].childNodes[0].nodeValue
            return OpenTokSession(session_id)
        except Exception, e:
            raise OpenTokException('Failed to generate session: %s' % str(e))

    def headers(self):
        return {
            'User-Agent': 'OpenTok-Python-SDK/' + __version__,
            'X-TB-PARTNER-AUTH': self.api_key + ':' + self.api_secret
        }

    def archive_headers(self):
        result = self.headers()
        result['Content-Type'] = 'application/json'
        return result

    def session_url(self):
        url = OpenTokSDK.API_URL + '/session/create'
        return url

    def archive_url(self, archive_id=None):
        url = OpenTokSDK.API_URL + '/v2/partner/' + self.api_key + '/archive'
        if archive_id:
            url = url + '/' + archive_id
        return url

    def start_archive(self, session_id, **kwargs):
        payload = {'name': kwargs.get('name'), 'sessionId': session_id}

        response = requests.post(self.archive_url(), data=json.dumps(payload), headers=self.archive_headers())

        if response.status_code < 300:
            return OpenTokArchive(self, response.json())
        elif response.status_code == 403:
            raise AuthError()
        elif response.status_code == 400:
            raise RequestError("Session ID is invalid")
        elif response.status_code == 404:
            raise NotFoundError("Session not found")
        elif response.status_code == 409:
            raise ArchiveError(response.json().get("message"))
        else:
            raise RequestError("An unexpected error occurred", response.status_code)

    def stop_archive(self, archive_id):
        response = requests.post(self.archive_url(archive_id) + '/stop', headers=self.archive_headers())

        if response.status_code < 300:
            return OpenTokArchive(self, response.json())
        elif response.status_code == 403:
            raise AuthError()
        elif response.status_code == 404:
            raise NotFoundError("Archive not found")
        elif response.status_code == 409:
            raise ArchiveError("Archive is not in started state")
        else:
            raise RequestError("An unexpected error occurred", response.status_code)

    def delete_archive(self, archive_id):
        response = requests.delete(self.archive_url(archive_id), headers=self.archive_headers())

        if response.status_code < 300:
            pass
        elif response.status_code == 403:
            raise AuthError()
        elif response.status_code == 404:
            raise NotFoundError("Archive not found")
        else:
            raise RequestError("An unexpected error occurred", response.status_code)

    def get_archive(self, archive_id):
        response = requests.get(self.archive_url(archive_id), headers=self.archive_headers())

        if response.status_code < 300:
            return OpenTokArchive(self, response.json())
        elif response.status_code == 403:
            raise AuthError()
        elif response.status_code == 404:
            raise NotFoundError("Archive not found")
        else:
            raise RequestError("An unexpected error occurred", response.status_code)

    def get_archives(self, offset=None, count=None):
        params = {}
        if offset is not None:
            params['offset'] = offset
        if count is not None:
            params['count'] = count

        response = requests.get(self.archive_url() + "?" + urllib.urlencode(params), headers=self.archive_headers())

        if response.status_code < 300:
            return OpenTokArchiveList(response.json())
        elif response.status_code == 403:
            raise AuthError()
        elif response.status_code == 404:
            raise NotFoundError("Archive not found")
        else:
            raise RequestError("An unexpected error occurred", response.status_code)

    def _sign_string(self, string, secret):
        return hmac.new(secret.encode('utf-8'), string.encode('utf-8'), hashlib.sha1).hexdigest()
