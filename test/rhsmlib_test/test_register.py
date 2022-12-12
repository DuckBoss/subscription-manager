from __future__ import print_function, division, absolute_import

#
# Copyright (c) 2016 Red Hat, Inc.
#
# This software is licensed to you under the GNU General Public License,
# version 2 (GPLv2). There is NO WARRANTY for this software, express or
# implied, including the implied warranties of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. You should have received a copy of GPLv2
# along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.
#
# Red Hat trademarks are not licensed under GPLv2. No permission is
# granted to use or replicate Red Hat trademarks that are incorporated
# in this software or its documentation.
#
import contextlib
import json
import socket
import tempfile
from typing import Optional

import mock

import subscription_manager.injection as inj

from subscription_manager.cache import InstalledProductsManager, ContentAccessModeCache
from subscription_manager.cp_provider import CPProvider
from subscription_manager.facts import Facts
from subscription_manager.identity import Identity
from subscription_manager.plugins import PluginManager

from ..fixture import set_up_mock_sp_store

from rhsm import connection

import rhsmlib
from rhsmlib.dbus.server import DomainSocketServer
from rhsmlib.dbus.objects import RegisterDBusObject, DomainSocketRegisterDBusObject
from rhsmlib.services import register, exceptions

from test.rhsmlib_test.base import DBusServerStubProvider, InjectionMockingTest

CONSUMER_CONTENT_JSON = '''{"hypervisorId": "foo",
        "serviceLevel": "",
        "autoheal": true,
        "idCert": {
          "key": "FAKE_KEY",
          "cert": "FAKE_CERT",
          "serial" : {
            "id" : 5196045143213189102,
            "revoked" : false,
            "collected" : false,
            "expiration" : "2033-04-25T18:03:06+0000",
            "serial" : 5196045143213189102,
            "created" : "2017-04-25T18:03:06+0000",
            "updated" : "2017-04-25T18:03:06+0000"
          },
          "id" : "8a8d011e5ba64700015ba647fbd20b88",
          "created" : "2017-04-25T18:03:07+0000",
          "updated" : "2017-04-25T18:03:07+0000"
        },
        "owner": {
          "href": "/owners/admin",
          "displayName": "Admin Owner",
          "id": "ff808081550d997c01550d9adaf40003",
          "key": "admin",
          "contentAccessMode": "entitlement"
        },
        "href": "/consumers/c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",
        "facts": {}, "id": "ff808081550d997c015511b0406d1065",
        "uuid": "c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",
        "guestIds": null, "capabilities": null,
        "environment": null, "installedProducts": null,
        "canActivate": false, "type": {"manifest": false,
        "id": "1000", "label": "system"}, "annotations": null,
        "username": "admin", "updated": "2016-06-02T15:16:51+0000",
        "lastCheckin": null, "entitlementCount": 0, "releaseVer":
        {"releaseVer": null}, "entitlementStatus": "valid", "name":
        "test.example.com", "created": "2016-06-02T15:16:51+0000",
        "contentTags": null, "dev": false}'''

CONSUMER_CONTENT_JSON_SCA = """{"hypervisorId": null,
        "serviceLevel": "",
        "autoheal": true,
        "idCert": {
          "key": "FAKE_KEY",
          "cert": "FAKE_CERT",
          "serial" : {
            "id" : 5196045143213189102,
            "revoked" : false,
            "collected" : false,
            "expiration" : "2033-04-25T18:03:06+0000",
            "serial" : 5196045143213189102,
            "created" : "2017-04-25T18:03:06+0000",
            "updated" : "2017-04-25T18:03:06+0000"
          },
          "id" : "8a8d011e5ba64700015ba647fbd20b88",
          "created" : "2017-04-25T18:03:07+0000",
          "updated" : "2017-04-25T18:03:07+0000"
        },
        "owner": {
          "href": "/owners/admin",
          "displayName": "Admin Owner",
          "id": "ff808081550d997c01550d9adaf40003",
          "key": "admin",
          "contentAccessMode": "org_environment"
        },
        "href": "/consumers/c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",
        "facts": {}, "id": "ff808081550d997c015511b0406d1065",
        "uuid": "c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",
        "guestIds": null, "capabilities": null,
        "environment": null, "installedProducts": null,
        "canActivate": false, "type": {"manifest": false,
        "id": "1000", "label": "system"}, "annotations": null,
        "username": "admin", "updated": "2016-06-02T15:16:51+0000",
        "lastCheckin": null, "entitlementCount": 0, "releaseVer":
        {"releaseVer": null}, "entitlementStatus": "valid", "name":
        "test.example.com", "created": "2016-06-02T15:16:51+0000",
        "contentTags": null, "dev": false}"""

ENABLED_CONTENT = """[ {
  "created" : "2022-06-30T13:24:33+0000",
  "updated" : "2022-06-30T13:24:33+0000",
  "id" : "16def3d98d6549f8a3649f723a76991c",
  "consumer" : {
    "id" : "4028face81aa047e0181b4c8e1170bdc",
    "uuid" : "8503a41a-6ce2-480c-bc38-b67d6aa6dd20",
    "name" : "thinkpad-t580",
    "href" : "/consumers/8503a41a-6ce2-480c-bc38-b67d6aa6dd20"
  },
  "pool" : {
    "created" : "2022-06-28T11:14:35+0000",
    "updated" : "2022-06-30T13:24:33+0000",
    "id" : "4028face81aa047e0181aa052f740360",
    "type" : "NORMAL",
    "owner" : {
      "id" : "4028face81aa047e0181aa0490e30002",
      "key" : "admin",
      "displayName" : "Admin Owner",
      "href" : "/owners/admin",
      "contentAccessMode" : "entitlement"
    },
    "activeSubscription" : true,
    "sourceEntitlement" : null,
    "quantity" : 5,
    "startDate" : "2022-06-23T13:14:26+0000",
    "endDate" : "2023-06-23T13:14:26+0000",
    "attributes" : [ ],
    "restrictedToUsername" : null,
    "contractNumber" : "0",
    "accountNumber" : "6547096716",
    "orderNumber" : "order-23226139",
    "consumed" : 1,
    "exported" : 0,
    "branding" : [ ],
    "calculatedAttributes" : {
      "compliance_type" : "Standard"
    },
    "upstreamPoolId" : "upstream-05736148",
    "upstreamEntitlementId" : null,
    "upstreamConsumerId" : null,
    "productName" : "SP Server Standard (U: Development, R: SP Server)",
    "productId" : "sp-server-dev",
    "productAttributes" : [ {
      "name" : "management_enabled",
      "value" : "1"
    }, {
      "name" : "usage",
      "value" : "Development"
    }, {
      "name" : "roles",
      "value" : "SP Server"
    }, {
      "name" : "variant",
      "value" : "ALL"
    }, {
      "name" : "sockets",
      "value" : "128"
    }, {
      "name" : "support_level",
      "value" : "Standard"
    }, {
      "name" : "support_type",
      "value" : "L1-L3"
    }, {
      "name" : "arch",
      "value" : "ALL"
    }, {
      "name" : "type",
      "value" : "MKT"
    }, {
      "name" : "version",
      "value" : "1.0"
    } ],
    "stackId" : null,
    "stacked" : false,
    "sourceStackId" : null,
    "developmentPool" : false,
    "href" : "/pools/4028face81aa047e0181aa052f740360",
    "derivedProductAttributes" : [ ],
    "derivedProductId" : null,
    "derivedProductName" : null,
    "providedProducts" : [ {
      "productId" : "99000",
      "productName" : "SP Server Bits"
    } ],
    "derivedProvidedProducts" : [ ],
    "subscriptionSubKey" : "master",
    "subscriptionId" : "srcsub-45255972",
    "locked" : false
  },
  "quantity" : 1,
  "certificates" : [ {
    "created" : "2022-06-30T13:24:33+0000",
    "updated" : "2022-06-30T13:24:33+0000",
    "id" : "4028face81aa047e0181b4c8e4b90be1",
    "key" : "-----BEGIN PRIVATE KEY-----REDACTED-----END PRIVATE KEY-----",
    "cert" : "-----BEGIN CERTIFICATE-----REDACTED-----END RSA SIGNATURE-----",
    "serial" : {
      "created" : "2022-06-30T13:24:33+0000",
      "updated" : "2022-06-30T13:24:33+0000",
      "id" : 3712610178651551557,
      "serial" : 3712610178651551557,
      "expiration" : "2023-06-23T13:14:26+0000",
      "revoked" : false
    }
  } ],
  "startDate" : "2022-06-23T13:14:26+0000",
  "endDate" : "2023-06-23T13:14:26+0000",
  "href" : null
} ]
"""

# Following consumer do not contain information about content access mode
OLD_CONSUMER_CONTENT_JSON = '''{"hypervisorId": null,
        "serviceLevel": "",
        "autoheal": true,
        "idCert": {
          "key": "FAKE_KEY",
          "cert": "FAKE_CERT",
          "serial" : {
            "id" : 5196045143213189102,
            "revoked" : false,
            "collected" : false,
            "expiration" : "2033-04-25T18:03:06+0000",
            "serial" : 5196045143213189102,
            "created" : "2017-04-25T18:03:06+0000",
            "updated" : "2017-04-25T18:03:06+0000"
          },
          "id" : "8a8d011e5ba64700015ba647fbd20b88",
          "created" : "2017-04-25T18:03:07+0000",
          "updated" : "2017-04-25T18:03:07+0000"
        },
        "owner": {
          "href": "/owners/admin",
          "displayName": "Admin Owner",
          "id": "ff808081550d997c01550d9adaf40003",
          "key": "admin"
        },
        "href": "/consumers/c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",
        "facts": {}, "id": "ff808081550d997c015511b0406d1065",
        "uuid": "c1b8648c-6f0a-4aa5-b34e-b9e62c0e4364",
        "guestIds": null, "capabilities": null,
        "environments": null, "installedProducts": null,
        "canActivate": false, "type": {"manifest": false,
        "id": "1000", "label": "system"}, "annotations": null,
        "username": "admin", "updated": "2016-06-02T15:16:51+0000",
        "lastCheckin": null, "entitlementCount": 0, "releaseVer":
        {"releaseVer": null}, "entitlementStatus": "valid", "name":
        "test.example.com", "created": "2016-06-02T15:16:51+0000",
        "contentTags": null, "dev": false}'''

OWNERS_CONTENT_JSON = '''[
    {
        "autobindDisabled": false,
        "autobindHypervisorDisabled": false,
        "contentAccessMode": "entitlement",
        "contentAccessModeList": "entitlement",
        "contentPrefix": null,
        "created": "2020-02-17T08:21:47+0000",
        "defaultServiceLevel": null,
        "displayName": "Donald Duck",
        "href": "/owners/donaldduck",
        "id": "ff80808170523d030170523d34890003",
        "key": "donaldduck",
        "lastRefreshed": null,
        "logLevel": null,
        "parentOwner": null,
        "updated": "2020-02-17T08:21:47+0000",
        "upstreamConsumer": null
    },
    {
        "autobindDisabled": false,
        "autobindHypervisorDisabled": false,
        "contentAccessMode": "entitlement",
        "contentAccessModeList": "entitlement",
        "contentPrefix": null,
        "created": "2020-02-17T08:21:47+0000",
        "defaultServiceLevel": null,
        "displayName": "Admin Owner",
        "href": "/owners/admin",
        "id": "ff80808170523d030170523d347c0002",
        "key": "admin",
        "lastRefreshed": null,
        "logLevel": null,
        "parentOwner": null,
        "updated": "2020-02-17T08:21:47+0000",
        "upstreamConsumer": null
    },
    {
        "autobindDisabled": false,
        "autobindHypervisorDisabled": false,
        "contentAccessMode": "entitlement",
        "contentAccessModeList": "entitlement,org_environment",
        "contentPrefix": null,
        "created": "2020-02-17T08:21:47+0000",
        "defaultServiceLevel": null,
        "displayName": "Snow White",
        "href": "/owners/snowwhite",
        "id": "ff80808170523d030170523d348a0004",
        "key": "snowwhite",
        "lastRefreshed": null,
        "logLevel": null,
        "parentOwner": null,
        "updated": "2020-02-17T08:21:47+0000",
        "upstreamConsumer": null
    }
]
'''


class RegisterServiceTest(InjectionMockingTest):
    def setUp(self):
        super(RegisterServiceTest, self).setUp()
        self.mock_identity = mock.Mock(spec=Identity, name="Identity")
        self.mock_cp = mock.Mock(spec=connection.UEPConnection, name="UEPConnection")

        # Mock a basic auth connection
        self.mock_cp.username = "username"
        self.mock_cp.password = "password"

        # Add a mock cp_provider
        self.mock_cp_provider = mock.Mock(spec=CPProvider, name="CPProvider")

        # Add a mock for content access mode cache
        self.mock_content_access_mode_cache = mock.Mock(
            spec=ContentAccessModeCache,
            name="ContentAccessModeCache"
        )
        self.mock_content_access_mode_cache.read_data = mock.Mock(return_value='entitlement')

        # For the tests in which it's used, the consumer_auth cp and basic_auth cp can be the same
        self.mock_cp_provider.get_consumer_auth_cp.return_value = self.mock_cp
        self.mock_cp_provider.get_basic_auth_cp.return_value = self.mock_cp

        self.mock_pm = mock.Mock(spec=PluginManager, name="PluginManager")
        self.mock_installed_products = mock.Mock(spec=InstalledProductsManager,
            name="InstalledProductsManager")
        self.mock_facts = mock.Mock(spec=Facts, name="Facts")
        self.mock_facts.get_facts.return_value = {}

        syspurpose_patch = mock.patch('subscription_manager.syspurposelib.SyncedStore')
        self.mock_sp_store = syspurpose_patch.start()
        self.mock_sp_store, self.mock_sp_store_contents = set_up_mock_sp_store(self.mock_sp_store)
        self.addCleanup(syspurpose_patch.stop)

        self.mock_syspurpose = mock.Mock()

    def injection_definitions(self, *args, **kwargs):
        if args[0] == inj.IDENTITY:
            return self.mock_identity
        elif args[0] == inj.PLUGIN_MANAGER:
            return self.mock_pm
        elif args[0] == inj.INSTALLED_PRODUCTS_MANAGER:
            return self.mock_installed_products
        elif args[0] == inj.FACTS:
            return self.mock_facts
        elif args[0] == inj.CP_PROVIDER:
            return self.mock_cp_provider
        elif args[0] == inj.CONTENT_ACCESS_MODE_CACHE:
            return self.mock_content_access_mode_cache
        else:
            return None

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_register_normally(self, mock_persist_consumer, mock_write_cache):
        self.mock_identity.is_valid.return_value = False
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []
        expected_consumer = json.loads(CONSUMER_CONTENT_JSON)
        self.mock_cp.registerConsumer.return_value = expected_consumer

        register_service = register.RegisterService(self.mock_cp)
        register_service.register("org", name="name", environments="environment")

        self.mock_cp.registerConsumer.assert_called_once_with(
            name="name",
            facts={},
            owner="org",
            environments="environment",
            keys=None,
            installed_products=[],
            jwt_token=None,
            content_tags=[],
            type="system",
            role="",
            addons=[],
            service_level="",
            usage="")
        self.mock_installed_products.write_cache.assert_called()

        mock_persist_consumer.assert_called_once_with(expected_consumer)
        mock_write_cache.assert_called_once()
        expected_plugin_calls = [
            mock.call('pre_register_consumer', name='name', facts={}),
            mock.call('post_register_consumer', consumer=expected_consumer, facts={})
        ]
        self.assertEqual(expected_plugin_calls, self.mock_pm.run.call_args_list)

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_register_normally_old_candlepin(self, mock_persist_consumer, mock_write_cache):
        """
        Test for the case, when candlepin server returns consumer without information about
        content access mode.
        """
        self.mock_identity.is_valid.return_value = False
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []
        expected_consumer = json.loads(OLD_CONSUMER_CONTENT_JSON)
        self.mock_cp.registerConsumer.return_value = expected_consumer

        register_service = register.RegisterService(self.mock_cp)
        consumer = register_service.register("org", name="name", environments="environments")

        self.mock_cp.registerConsumer.assert_called_once_with(
            name="name",
            facts={},
            owner="org",
            environments="environments",
            keys=None,
            installed_products=[],
            jwt_token=None,
            content_tags=[],
            type="system",
            role="",
            addons=[],
            service_level="",
            usage="")
        self.mock_installed_products.write_cache.assert_called()

        mock_persist_consumer.assert_called_once_with(expected_consumer)
        mock_write_cache.assert_called_once()
        expected_plugin_calls = [
            mock.call('pre_register_consumer', name='name', facts={}),
            mock.call('post_register_consumer', consumer=expected_consumer, facts={})
        ]
        self.assertEqual(expected_plugin_calls, self.mock_pm.run.call_args_list)
        assert 'owner' in consumer
        assert 'contentAccessMode' in consumer['owner']
        assert 'entitlement' == consumer['owner']['contentAccessMode']

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_register_normally_no_owner(self, mock_persist_consumer, mock_write_cache):
        """
        Test for the case, when candlepin server returns consumer without owner
        """
        self.mock_identity.is_valid.return_value = False
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []
        expected_consumer = json.loads(OLD_CONSUMER_CONTENT_JSON)
        del expected_consumer['owner']
        self.mock_cp.registerConsumer.return_value = expected_consumer

        register_service = register.RegisterService(self.mock_cp)
        consumer = register_service.register("org", name="name", environments="environments")

        self.mock_cp.registerConsumer.assert_called_once_with(
            name="name",
            facts={},
            owner="org",
            environments="environments",
            keys=None,
            installed_products=[],
            jwt_token=None,
            content_tags=[],
            type="system",
            role="",
            addons=[],
            service_level="",
            usage="")
        self.mock_installed_products.write_cache.assert_called()

        mock_persist_consumer.assert_called_once_with(expected_consumer)
        mock_write_cache.assert_called_once()
        expected_plugin_calls = [
            mock.call('pre_register_consumer', name='name', facts={}),
            mock.call('post_register_consumer', consumer=expected_consumer, facts={})
        ]
        self.assertEqual(expected_plugin_calls, self.mock_pm.run.call_args_list)
        assert 'owner' not in consumer

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_register_normally_with_no_org_specified(self, mock_persist_consumer, mock_write_cache):
        """
        This test is intended for the case, when no organization is specified, but user is member
        only of one organization and thus it can be automatically selected
        """
        self.mock_cp.getOwnerList = mock.Mock()
        self.mock_cp.getOwnerList.return_value = [
            {
                "created": "2020-08-18T07:57:47+0000",
                "updated": "2020-08-18T07:57:47+0000",
                "id": "ff808081740092cd01740092fe540002",
                "key": "snowwhite",
                "displayName": "Snow White",
                "parentOwner": None,
                "contentPrefix": None,
                "defaultServiceLevel": None,
                "upstreamConsumer": None,
                "logLevel": None,
                "autobindDisabled": False,
                "autobindHypervisorDisabled": False,
                "contentAccessMode": "entitlement",
                "contentAccessModeList": "entitlement,org_environment",
                "lastRefreshed": None,
                "href": "/owners/snowwhite"
            }
        ]
        self.mock_identity.is_valid.return_value = False
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []
        expected_consumer = json.loads(CONSUMER_CONTENT_JSON)
        self.mock_cp.registerConsumer.return_value = expected_consumer

        register_service = register.RegisterService(self.mock_cp)

        def _get_owner_cb(orgs):
            pass

        def _no_owner_cb(username):
            pass

        org = register_service.determine_owner_key(
            username=self.mock_cp.username,
            get_owner_cb=_get_owner_cb,
            no_owner_cb=_no_owner_cb
        )

        self.assertIsNotNone(org)

        register_service.register(org, name="name", environments="environment")

        self.mock_cp.registerConsumer.assert_called_once_with(
            name="name",
            facts={},
            owner="snowwhite",
            environments="environment",
            keys=None,
            installed_products=[],
            jwt_token=None,
            content_tags=[],
            type="system",
            role="",
            addons=[],
            service_level="",
            usage="")
        self.mock_installed_products.write_cache.assert_called()

        mock_persist_consumer.assert_called_once_with(expected_consumer)
        mock_write_cache.assert_called_once()
        expected_plugin_calls = [
            mock.call('pre_register_consumer', name='name', facts={}),
            mock.call('post_register_consumer', consumer=expected_consumer, facts={})
        ]
        self.assertEqual(expected_plugin_calls, self.mock_pm.run.call_args_list)

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_register_with_activation_keys(self, mock_persist_consumer, mock_write_cache):
        self.mock_cp.username = None
        self.mock_cp.password = None
        self.mock_identity.is_valid.return_value = False
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []

        expected_consumer = json.loads(CONSUMER_CONTENT_JSON)
        self.mock_cp.registerConsumer.return_value = expected_consumer

        register_service = register.RegisterService(self.mock_cp)
        register_service.register("org", name="name", activation_keys=[1])

        self.mock_cp.registerConsumer.assert_called_once_with(
            name="name",
            facts={},
            owner="org",
            environments=None,
            keys=[1],
            installed_products=[],
            jwt_token=None,
            content_tags=[],
            type="system",
            role="",
            addons=[],
            service_level="",
            usage=""
        )
        self.mock_installed_products.write_cache.assert_called()

        mock_persist_consumer.assert_called_once_with(expected_consumer)
        mock_write_cache.assert_called_once()
        expected_plugin_calls = [
            mock.call('pre_register_consumer', name='name', facts={}),
            mock.call('post_register_consumer', consumer=expected_consumer, facts={})
        ]
        self.assertEqual(expected_plugin_calls, self.mock_pm.run.call_args_list)

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_register_with_consumerid(self, mock_persist_consumer, mock_write_cache):
        self.mock_identity.is_valid.return_value = False
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []

        expected_consumer = json.loads(CONSUMER_CONTENT_JSON)
        self.mock_cp.getConsumer.return_value = json.loads(CONSUMER_CONTENT_JSON)

        register_service = register.RegisterService(self.mock_cp)
        register_service.register("org", name="name", consumerid="consumerid")

        self.mock_cp.getConsumer.assert_called_once_with("consumerid")
        self.mock_installed_products.write_cache.assert_called()

        mock_persist_consumer.assert_called_once_with(expected_consumer)
        mock_write_cache.assert_called_once()
        expected_plugin_calls = [
            mock.call('pre_register_consumer', name='name', facts={}),
            mock.call('post_register_consumer', consumer=expected_consumer, facts={})
        ]
        self.assertEqual(expected_plugin_calls, self.mock_pm.run.call_args_list)

    def _build_options(self, activation_keys=None, environments=None, force=None, name=None, consumerid=None):
        return {
            'activation_keys': activation_keys,
            'environments': environments,
            'force': force,
            'name': name,
            'consumerid': consumerid
        }

    def test_fails_when_previously_registered(self):
        self.mock_identity.is_valid.return_value = True

        with self.assertRaisesRegexp(exceptions.ValidationError, r'.*system is already registered.*'):
            register.RegisterService(self.mock_cp).validate_options(self._build_options())

    def test_allows_force(self):
        self.mock_identity.is_valid.return_value = True
        options = self._build_options(force=True)
        register.RegisterService(self.mock_cp).validate_options(options)

    @mock.patch("rhsmlib.services.register.syspurposelib.write_syspurpose_cache", return_value=True)
    @mock.patch("rhsmlib.services.register.managerlib.persist_consumer_cert")
    def test_reads_syspurpose(self, mock_persist_consumer, mock_write_cache):
        self.mock_installed_products.format_for_server.return_value = []
        self.mock_installed_products.tags = []
        self.mock_identity.is_valid.return_value = False
        self.mock_sp_store_contents["role"] = "test_role"
        self.mock_sp_store_contents["service_level_agreement"] = "test_sla"
        self.mock_sp_store_contents["addons"] = ["addon1"]
        self.mock_sp_store_contents["usage"] = "test_usage"

        expected_consumer = json.loads(CONSUMER_CONTENT_JSON)
        self.mock_cp.registerConsumer.return_value = expected_consumer

        register_service = register.RegisterService(self.mock_cp)
        register_service.register("org", name="name")

        self.mock_cp.registerConsumer.assert_called_once_with(
            addons=["addon1"],
            content_tags=[],
            environments=None,
            facts={},
            installed_products=[],
            jwt_token=None,
            keys=None,
            name="name",
            owner="org",
            role="test_role",
            service_level="test_sla",
            type="system",
            usage="test_usage")
        mock_write_cache.assert_called_once()

    def test_does_not_require_basic_auth_with_activation_keys(self):
        self.mock_cp.username = None
        self.mock_cp.password = None

        self.mock_identity.is_valid.return_value = False
        options = self._build_options(activation_keys=[1])
        register.RegisterService(self.mock_cp).validate_options(options)

    def test_does_not_allow_basic_auth_with_activation_keys(self):
        self.mock_identity.is_valid.return_value = False
        options = self._build_options(activation_keys=[1])
        with self.assertRaisesRegexp(exceptions.ValidationError, r'.*do not require user credentials.*'):
            register.RegisterService(self.mock_cp).validate_options(options)

    def test_does_not_allow_environment_with_activation_keys(self):
        self.mock_cp.username = None
        self.mock_cp.password = None

        self.mock_identity.is_valid.return_value = False
        options = self._build_options(activation_keys=[1], environments='environment')
        with self.assertRaisesRegexp(exceptions.ValidationError, r'.*do not allow environments.*'):
            register.RegisterService(self.mock_cp).validate_options(options)

    def test_does_not_allow_environment_with_consumerid(self):
        self.mock_cp.username = None
        self.mock_cp.password = None

        self.mock_identity.is_valid.return_value = False
        options = self._build_options(activation_keys=[1], consumerid='consumerid')
        with self.assertRaisesRegexp(exceptions.ValidationError, r'.*previously registered.*'):
            register.RegisterService(self.mock_cp).validate_options(options)

    def test_requires_basic_auth_for_normal_registration(self):
        self.mock_cp.username = None
        self.mock_cp.password = None

        self.mock_identity.is_valid.return_value = False
        options = self._build_options(consumerid='consumerid')
        with self.assertRaisesRegexp(exceptions.ValidationError, r'.*Missing username.*'):
            register.RegisterService(self.mock_cp).validate_options(options)


class RegisterDBusObjectTest(DBusServerStubProvider):
    dbus_class = RegisterDBusObject
    dbus_class_kwargs = {}
    socket_dir: Optional[tempfile.TemporaryDirectory] = None

    def setUp(self) -> None:
        self.socket_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.socket_dir.cleanup)

        socket_path_patch = mock.patch.object(DomainSocketServer, "_server_socket_path", self.socket_dir.name)
        socket_path_patch.start()
        # `tmpdir` behaves differently from `dir` on old versions of dbus
        # (earlier than 1.12.24 and 1.14.4).
        # In newer versions we are not getting abstract socket anymore.
        socket_iface_patch = mock.patch.object(DomainSocketServer, "_server_socket_iface", "unix:dir=")
        socket_iface_patch.start()

        super().setUp()

    def tearDown(self) -> None:
        """Make sure the domain server is stopped once the test ends."""
        with contextlib.suppress(rhsmlib.dbus.exceptions.Failed):
            self.obj.Stop.__wrapped__(self.obj, self.LOCALE)

        super().tearDown()

    def test_Start(self):
        substring = self.socket_dir.name + "/dbus.*"
        result = self.obj.Start.__wrapped__(self.obj, self.LOCALE)
        self.assertRegex(result, substring)

    def test_Start__two_starts(self):
        """Test that opening the server twice returns the same address"""
        result_1 = self.obj.Start.__wrapped__(self.obj, self.LOCALE)
        result_2 = self.obj.Start.__wrapped__(self.obj, self.LOCALE)
        self.assertEqual(result_1, result_2)

    def test_Start__can_connect(self):
        result = self.obj.Start.__wrapped__(self.obj, self.LOCALE)
        prefix, _, data = result.partition("=")
        address, _, guid = data.partition(",")

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(address)
        finally:
            sock.close()

    def test_Stop(self):
        self.obj.Start.__wrapped__(self.obj, self.LOCALE)
        self.obj.Stop.__wrapped__(self.obj, self.LOCALE)

    def test_Stop__not_running(self):
        with self.assertRaises(rhsmlib.dbus.exceptions.Failed):
            self.obj.Stop.__wrapped__(self.obj, self.LOCALE)


class DomainSocketRegisterDBusObjectTest(DBusServerStubProvider):
    dbus_class = DomainSocketRegisterDBusObject
    dbus_class_kwargs = {}

    @classmethod
    def setUpClass(cls) -> None:
        register_patch = mock.patch(
            "rhsmlib.dbus.objects.register.RegisterService.register",
            name="register",
        )
        cls.patches["register"] = register_patch.start()
        cls.addClassCleanup(register_patch.stop)

        is_registered_patch = mock.patch(
            "rhsmlib.dbus.base_object.BaseObject.is_registered",
            name="is_registered",
        )
        cls.patches["is_registered"] = is_registered_patch.start()
        cls.addClassCleanup(is_registered_patch.stop)

        update_patch = mock.patch(
            "rhsmlib.dbus.objects.register.EntCertActionInvoker.update",
            name="update",
        )
        cls.patches["update"] = update_patch.start()
        cls.addClassCleanup(update_patch.stop)

        attach_auto_patch = mock.patch(
            "rhsmlib.dbus.objects.register.AttachService.attach_auto",
            name="attach_auto",
        )
        cls.patches["attach_auto"] = attach_auto_patch.start()
        cls.addClassCleanup(attach_auto_patch.stop)

        build_uep_patch = mock.patch(
            "rhsmlib.dbus.base_object.BaseObject.build_uep",
            name="build_uep",
        )
        cls.patches["build_uep"] = build_uep_patch.start()
        cls.addClassCleanup(build_uep_patch.stop)

        super().setUpClass()

    def setUp(self) -> None:
        self.patches["update"].return_value = None

        super().setUp()

    def test_Register(self):
        expected = json.loads(CONSUMER_CONTENT_JSON)
        self.patches["register"].return_value = expected
        self.patches["is_registered"].return_value = False

        result = self.obj.Register.__wrapped__(self.obj, "org", "username", "password", {}, {}, self.LOCALE)
        self.assertEqual(expected, json.loads(result))

    def test_Register__enable_content(self):
        """Test including 'enable_content' in entitlement mode with no content."""
        expected = json.loads(CONSUMER_CONTENT_JSON)
        self.patches["register"].return_value = expected
        self.patches["attach_auto"].return_value = []
        self.patches["is_registered"].return_value = False

        result = self.obj.Register.__wrapped__(
            self.obj, "org", "username", "password", {"enable_content": "1"}, {}, self.LOCALE
        )
        self.assertEqual(expected, json.loads(result))

    def test_Register__enable_content_with_content(self):
        """Test including 'enable_content' in entitlement mode with some content."""
        expected = json.loads(ENABLED_CONTENT)
        self.patches["register"].return_value = json.loads(CONSUMER_CONTENT_JSON)
        self.patches["attach_auto"].return_value = expected
        self.patches["is_registered"].return_value = False

        result = self.obj.Register.__wrapped__(
            self.obj, "org", "username", "password", {"enable_content": "1"}, {}, self.LOCALE
        )
        self.assertEqual(expected, json.loads(result)["enabledContent"])

    def test_Register__enable_content__sca(self):
        """Test including 'enable_content' in SCA mode."""
        expected = json.loads(CONSUMER_CONTENT_JSON_SCA)
        self.patches["register"].return_value = expected
        self.patches["is_registered"].return_value = False

        result = self.obj.Register.__wrapped__(
            self.obj, "org", "username", "password", {"enable_content": "1"}, {}, self.LOCALE
        )
        self.assertEqual(expected, json.loads(result))

    def test_GetOrgs(self):
        self.patches["is_registered"].return_value = False
        mock_cp = mock.Mock(spec=connection.UEPConnection, name="UEPConnection")
        mock_cp.username = "username"
        mock_cp.password = "password"
        mock_cp.getOwnerList = mock.Mock()
        mock_cp.getOwnerList.return_value = json.loads(OWNERS_CONTENT_JSON)
        self.patches["build_uep"].return_value = mock_cp

        expected = json.loads(OWNERS_CONTENT_JSON)
        result = self.obj.GetOrgs.__wrapped__(self.obj, "username", "password", {}, self.LOCALE)
        self.assertEqual(expected, json.loads(result))

    def test_RegisterWithActivationKeys(self):
        expected = json.loads(CONSUMER_CONTENT_JSON)
        self.patches["is_registered"].return_value = False
        self.patches["register"].return_value = expected

        result = self.obj.RegisterWithActivationKeys.__wrapped__(
            self.obj,
            "username",
            ["key1", "key2"],
            {},
            {"host": "localhost", "port": "8443", "handler": "/candlepin"},
            self.LOCALE,
        )
        self.assertEqual(expected, json.loads(result))
