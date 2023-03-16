# Copyright (c) 2017 Red Hat, Inc.
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
import dbus
import json
import mock

from test.rhsmlib.base import DBusObjectTest, InjectionMockingTest

from subscription_manager import injection as inj
from subscription_manager.cp_provider import CPProvider

from rhsmlib.dbus.objects import AttachDBusObject
from rhsmlib.dbus import constants

from test import subman_marker_dbus


CONTENT_JSON = [
    {
        "id": "19ec0d4f93ae47e18233b2590b3e71f3",
        "consumer": {
            "id": "8a8d01865d2cb201015d331b0078006a",
            "uuid": "47680d96-cfa4-4326-b545-5a6e02a4e95a",
            "name": "orgBConsumer-tZTbHviW",
            "href": "/consumers/47680d96-cfa4-4326-b545-5a6e02a4e95a",
        },
        "pool": {
            "id": "8a8d01865d2cb201015d331b01b6006f",
            "type": "NORMAL",
            "owner": {
                "id": "8a8d01865d2cb201015d331afec50059",
                "key": "orgB-txDmAJWq",
                "displayName": "orgB-txDmAJWq",
                "href": "/owners/orgB-txDmAJWq",
            },
            "activeSubscription": True,
            "quantity": 1,
            "startDate": "2017-07-11T19:23:14+0000",
            "endDate": "2018-07-11T19:23:14+0000",
            "attributes": [],
            "consumed": 1,
            "exported": 0,
            "shared": 0,
            "branding": [],
            "calculatedAttributes": {"compliance_type": "Standard"},
            "productId": "prod-25G4r19T",
            "productAttributes": [{"name": "type", "value": "SVC"}],
            "derivedProductAttributes": [],
            "productName": "prod-Fz0IBfN6",
            "stacked": False,
            "developmentPool": False,
            "href": "/pools/8a8d01865d2cb201015d331b01b6006f",
            "created": "2017-07-11T19:23:14+0000",
            "updated": "2017-07-11T19:23:14+0000",
            "providedProducts": [],
            "derivedProvidedProducts": [],
            "subscriptionId": "source_sub_-LO4l9YKv",
            "subscriptionSubKey": "master",
        },
        "certificates": [
            {
                "key": "FAKE KEY",
                "cert": "FAKE_CERT",
                "serial": {
                    "id": 7020569423934353740,
                    "revoked": False,
                    "collected": False,
                    "expiration": "2018-07-11T19:23:14+0000",
                    "serial": 7020569423934353740,
                    "created": "2017-07-11T19:23:14+0000",
                    "updated": "2017-07-11T19:23:14+0000",
                },
                "id": "8a8d01865d2cb201015d331b02870072",
                "created": "2017-07-11T19:23:14+0000",
                "updated": "2017-07-11T19:23:14+0000",
            }
        ],
        "quantity": 1,
        "startDate": "2017-07-11T19:23:14+0000",
        "endDate": "2018-07-11T19:23:14+0000",
        "href": "/entitlements/19ec0d4f93ae47e18233b2590b3e71f3",
        "created": "2017-07-11T19:23:14+0000",
        "updated": "2017-07-11T19:23:14+0000",
    }
]


@subman_marker_dbus
class TestAttachDBusObject(DBusObjectTest, InjectionMockingTest):
    def setUp(self):
        super(TestAttachDBusObject, self).setUp()
        self.proxy = self.proxy_for(AttachDBusObject.default_dbus_path)
        self.interface = dbus.Interface(self.proxy, constants.ATTACH_INTERFACE)

        attach_patcher = mock.patch("rhsmlib.dbus.objects.attach.AttachService", autospec=True)
        self.mock_attach = attach_patcher.start().return_value
        self.addCleanup(attach_patcher.stop)

        entcertlib_patcher = mock.patch("rhsmlib.dbus.objects.attach.entcertlib.EntCertActionInvoker")
        self.mock_action_invoker = entcertlib_patcher.start().return_value
        self.addCleanup(entcertlib_patcher.stop)

        self.mock_identity.is_valid.return_value = True
        self.mock_identity.uuid = "id"

        is_simple_content_access_patcher = mock.patch("rhsmlib.dbus.objects.attach.is_simple_content_access")
        self.mock_is_simple_content_access = is_simple_content_access_patcher.start()
        self.mock_is_simple_content_access.return_value = False
        self.addCleanup(is_simple_content_access_patcher.stop)

    def injection_definitions(self, *args, **kwargs):
        if args[0] == inj.IDENTITY:
            return self.mock_identity
        elif args[0] == inj.CP_PROVIDER:
            provider = mock.Mock(spec=CPProvider, name="CPProvider").return_value
            provider.get_consumer_auth_cp.return_value = mock.Mock(name="MockCP")
            return provider
        else:
            return None

    def dbus_objects(self):
        return [AttachDBusObject]

    def test_pool_attach(self):
        def assertions(*args):
            expected_content = [json.dumps(CONTENT_JSON), json.dumps(CONTENT_JSON)]
            result = args[0]
            self.assertEqual(result, expected_content)

        self.mock_attach.attach_pool.return_value = CONTENT_JSON

        dbus_method_args = [["x", "y"], 1, {}, ""]
        self.dbus_request(assertions, self.interface.PoolAttach, dbus_method_args)

    def test_pool_attach_using_proxy(self):
        def assertions(*args):
            expected_content = [json.dumps(CONTENT_JSON), json.dumps(CONTENT_JSON)]
            result = args[0]
            self.assertEqual(result, expected_content)

        self.mock_attach.attach_pool.return_value = CONTENT_JSON

        dbus_method_args = [
            ["x", "y"],
            1,
            {
                "proxy_hostname": "proxy.company.com",
                "proxy_port": "3128",
                "proxy_user": "user",
                "proxy_password": "secret",
            },
            "",
        ]
        self.dbus_request(assertions, self.interface.PoolAttach, dbus_method_args)

    def test_pool_germany_attach(self):
        def assertions(*args):
            expected_content = [json.dumps(CONTENT_JSON), json.dumps(CONTENT_JSON)]
            result = args[0]
            self.assertEqual(result, expected_content)

        self.mock_attach.attach_pool.return_value = CONTENT_JSON

        dbus_method_args = [["x", "y"], 1, {}, "de"]
        self.dbus_request(assertions, self.interface.PoolAttach, dbus_method_args)

    def test_pool_germany_GERMANY__attach(self):
        def assertions(*args):
            expected_content = [json.dumps(CONTENT_JSON), json.dumps(CONTENT_JSON)]
            result = args[0]
            self.assertEqual(result, expected_content)

        self.mock_attach.attach_pool.return_value = CONTENT_JSON

        dbus_method_args = [["x", "y"], 1, {}, "de_DE"]
        self.dbus_request(assertions, self.interface.PoolAttach, dbus_method_args)

    def test_pool_germany_utf8_attach(self):
        def assertions(*args):
            expected_content = [json.dumps(CONTENT_JSON), json.dumps(CONTENT_JSON)]
            result = args[0]
            self.assertEqual(result, expected_content)

        self.mock_attach.attach_pool.return_value = CONTENT_JSON

        dbus_method_args = [["x", "y"], 1, {}, "de_DE.utf-8"]
        self.dbus_request(assertions, self.interface.PoolAttach, dbus_method_args)

    def test_pool_germany_UTF8_attach(self):
        def assertions(*args):
            expected_content = [json.dumps(CONTENT_JSON), json.dumps(CONTENT_JSON)]
            result = args[0]
            self.assertEqual(result, expected_content)

        self.mock_attach.attach_pool.return_value = CONTENT_JSON

        dbus_method_args = [["x", "y"], 1, {}, "de_DE.UTF-8"]
        self.dbus_request(assertions, self.interface.PoolAttach, dbus_method_args)

    def test_must_be_registered_pool(self):
        self.mock_identity.is_valid.return_value = False
        pool_method_args = [["x", "y"], 1, {}, ""]
        with self.assertRaisesRegex(dbus.DBusException, r"requires the consumer to be registered.*"):
            self.dbus_request(None, self.interface.PoolAttach, pool_method_args)

    def test_must_be_registered_auto(self):
        self.mock_identity.is_valid.return_value = False
        auto_method_args = ["service_level", {}, ""]
        with self.assertRaisesRegex(dbus.DBusException, r"requires the consumer to be registered.*"):
            self.dbus_request(None, self.interface.AutoAttach, auto_method_args)

    @mock.patch("rhsmlib.dbus.objects.attach.is_simple_content_access")
    def test_auto_attach(self, mock_is_simple_content_access):
        """
        Test calling AutoAttach method in non-SCA mode
        """
        mock_is_simple_content_access.return_value = False

        def assertions(*args):
            result = args[0]
            self.assertEqual(result, json.dumps(CONTENT_JSON))

        self.mock_attach.attach_auto.return_value = CONTENT_JSON

        dbus_method_args = ["service_level", {}, ""]
        self.dbus_request(assertions, self.interface.AutoAttach, dbus_method_args)

    def test_auto_attach_sca(self):
        """
        Test that calling AutoAttach method raises exception, when system is in SCA mode
        """
        self.mock_is_simple_content_access.return_value = True

        self.mock_attach.attach_auto.return_value = CONTENT_JSON

        dbus_method_args = ["service_level", {}, ""]

        # TODO: change following code to assert, when calling AutoAttach will not be supported in SCA mode
        # with self.assertRaises(dbus.exceptions.DBusException):
        #     self.dbus_request(None, self.interface.AutoAttach, dbus_method_args)
        self.dbus_request(None, self.interface.AutoAttach, dbus_method_args)

    def test_attach_pool_sca(self):
        """
        Test that calling PoolAttach method raises exception in SCA mode
        """
        self.mock_is_simple_content_access.return_value = True

        self.mock_attach.attach_pool.return_value = CONTENT_JSON
        dbus_method_args = [["x", "y"], 1, {}, ""]

        # TODO: change following code to assert, when calling PoolAttach will not be supported in SCA mode
        # with self.assertRaises(dbus.exceptions.DBusException):
        #     self.dbus_request(None, self.interface.PoolAttach, dbus_method_args)
        self.dbus_request(None, self.interface.PoolAttach, dbus_method_args)
