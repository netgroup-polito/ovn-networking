#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

import mock

from neutron.agent.ovsdb.native import idlutils

from networking_ovn.common import acl as ovn_acl
from networking_ovn.common import constants as ovn_const
from networking_ovn.common import utils as ovn_utils
from networking_ovn.ovsdb import commands
from networking_ovn.tests import base
from networking_ovn.tests.unit import fakes


class TestBaseCommandHelpers(base.TestCase):
    def setUp(self):
        super(TestBaseCommandHelpers, self).setUp()
        self.column = 'ovn'
        self.new_value = '1'
        self.old_value = '2'

    def _get_fake_row_mutate(self):
        return fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={self.column: []},
            methods={'addvalue': None, 'delvalue': None})

    def _get_fake_row_no_mutate(self, column_value=None):
        column_value = column_value or []
        return fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={self.column: column_value})

    def test__addvalue_to_list_mutate(self):
        fake_row_mutate = self._get_fake_row_mutate()
        commands._addvalue_to_list(
            fake_row_mutate, self.column, self.new_value)
        fake_row_mutate.addvalue.assert_called_once_with(
            self.column, self.new_value)
        fake_row_mutate.verify.assert_not_called()

    def test__addvalue_to_list_force_no_mutate(self):
        fake_row_mutate = self._get_fake_row_mutate()
        commands._addvalue_to_list(
            fake_row_mutate, self.column, self.new_value,
            mutate=False)
        fake_row_mutate.addvalue.assert_not_called()
        fake_row_mutate.verify.assert_called_once_with(self.column)

    def _test__addvalue_to_list_no_mutate(self, fake_row):
        commands._addvalue_to_list(fake_row, self.column, self.new_value)
        fake_row.verify.assert_called_once_with(self.column)
        self.assertEqual([self.new_value], fake_row.ovn)

    def test__addvalue_to_list_new_no_mutate(self):
        fake_row_new = self._get_fake_row_no_mutate()
        self._test__addvalue_to_list_no_mutate(fake_row_new)

    def test__addvalue_to_list_exists_no_mutate(self):
        fake_row_exists = self._get_fake_row_no_mutate(
            column_value=[self.new_value])
        self._test__addvalue_to_list_no_mutate(fake_row_exists)

    def test__delvalue_from_list_mutate(self):
        fake_row_mutate = self._get_fake_row_mutate()
        commands._delvalue_from_list(
            fake_row_mutate, self.column, self.old_value)
        fake_row_mutate.delvalue.assert_called_once_with(
            self.column, self.old_value)
        fake_row_mutate.verify.assert_not_called()

    def test__delvalue_from_list_force_no_mutate(self):
        fake_row_mutate = self._get_fake_row_mutate()
        commands._delvalue_from_list(
            fake_row_mutate, self.column, self.old_value,
            mutate=False)
        fake_row_mutate.delvalue.assert_not_called()
        fake_row_mutate.verify.assert_called_once_with(self.column)

    def _test__delvalue_from_list_no_mutate(self, fake_row):
        commands._delvalue_from_list(fake_row, self.column, self.old_value)
        fake_row.verify.assert_called_once_with(self.column)
        self.assertEqual([], fake_row.ovn)

    def test__delvalue_from_list_new_no_mutate(self):
        fake_row_new = self._get_fake_row_no_mutate()
        self._test__delvalue_from_list_no_mutate(fake_row_new)

    def test__delvalue_from_list_exists_no_mutate(self):
        fake_row_exists = self._get_fake_row_no_mutate(
            column_value=[self.old_value])
        self._test__delvalue_from_list_no_mutate(fake_row_exists)

    def test__updatevalues_in_list_empty_mutate(self):
        fake_row_mutate = self._get_fake_row_mutate()
        commands._updatevalues_in_list(fake_row_mutate, self.column, [], [])
        fake_row_mutate.addvalue.assert_not_called()
        fake_row_mutate.delvalue.assert_not_called()
        fake_row_mutate.verify.assert_not_called()

    def test__updatevalues_in_list_mutate(self):
        fake_row_mutate = self._get_fake_row_mutate()
        commands._updatevalues_in_list(
            fake_row_mutate, self.column,
            new_values=[self.new_value],
            old_values=[self.old_value])
        fake_row_mutate.addvalue.assert_called_once_with(
            self.column, self.new_value)
        fake_row_mutate.delvalue.assert_called_once_with(
            self.column, self.old_value)
        fake_row_mutate.verify.assert_not_called()

    def test__updatevalues_in_list_empty_no_mutate(self):
        fake_row_no_mutate = self._get_fake_row_no_mutate()
        commands._updatevalues_in_list(fake_row_no_mutate, self.column, [], [])
        fake_row_no_mutate.verify.assert_called_once_with(self.column)
        self.assertEqual([], fake_row_no_mutate.ovn)

    def _test__updatevalues_in_list_no_mutate(self, fake_row):
        commands._updatevalues_in_list(
            fake_row, self.column,
            new_values=[self.new_value],
            old_values=[self.old_value])
        fake_row.verify.assert_called_once_with(self.column)
        self.assertEqual([self.new_value], fake_row.ovn)

    def test__updatevalues_in_list_new_no_mutate(self):
        fake_row_new = self._get_fake_row_no_mutate()
        self._test__updatevalues_in_list_no_mutate(fake_row_new)

    def test__updatevalues_in_list_exists_no_mutate(self):
        fake_row_exists = self._get_fake_row_no_mutate(
            column_value=[self.old_value, self.new_value])
        self._test__updatevalues_in_list_no_mutate(fake_row_exists)


class TestBaseCommand(base.TestCase):
    def setUp(self):
        super(TestBaseCommand, self).setUp()
        self.ovn_api = fakes.FakeOvsdbNbOvnIdl()
        self.transaction = fakes.FakeOvsdbTransaction()
        self.ovn_api.transaction = self.transaction


class TestAddLSwitchCommand(TestBaseCommand):

    def test_lswitch_exists(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=mock.ANY):
            cmd = commands.AddLSwitchCommand(
                self.ovn_api, 'fake-lswitch', may_exist=True, foo='bar')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_not_called()

    def test_lswitch_add_exists(self):
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api._tables['Logical_Switch'].rows[fake_lswitch.uuid] = \
            fake_lswitch
        self.transaction.insert.return_value = fake_lswitch
        cmd = commands.AddLSwitchCommand(
            self.ovn_api, fake_lswitch.name, may_exist=False)
        cmd.run_idl(self.transaction)
        # NOTE(rtheis): Mocking the transaction allows this insert
        # to succeed when it normally would fail due the duplicate name.
        self.transaction.insert.assert_called_once_with(
            self.ovn_api._tables['Logical_Switch'])

    def _test_lswitch_add(self, may_exist=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=None):
            fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
            self.transaction.insert.return_value = fake_lswitch
            cmd = commands.AddLSwitchCommand(
                self.ovn_api, 'fake-lswitch', may_exist=may_exist, foo='bar')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Logical_Switch'])
            self.assertEqual('fake-lswitch', fake_lswitch.name)
            self.assertEqual('bar', fake_lswitch.foo)

    def test_lswitch_add_may_exist(self):
        self._test_lswitch_add(may_exist=True)

    def test_lswitch_add_ignore_exists(self):
        self._test_lswitch_add(may_exist=False)


class TestDelLSwitchCommand(TestBaseCommand):

    def _test_lswitch_del_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelLSwitchCommand(
                self.ovn_api, 'fake-lswitch', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_no_exist_ignore(self):
        self._test_lswitch_del_no_exist(if_exists=True)

    def test_lswitch_no_exist_fail(self):
        self._test_lswitch_del_no_exist(if_exists=False)

    def test_lswitch_del(self):
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api._tables['Logical_Switch'].rows[fake_lswitch.uuid] = \
            fake_lswitch
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            cmd = commands.DelLSwitchCommand(
                self.ovn_api, fake_lswitch.name, if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lswitch.delete.assert_called_once_with()


class TestLSwitchSetExternalIdCommand(TestBaseCommand):

    def _test_lswitch_extid_update_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.LSwitchSetExternalIdCommand(
                self.ovn_api, 'fake-lswitch',
                ovn_const.OVN_NETWORK_NAME_EXT_ID_KEY, 'neutron-network',
                if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_no_exist_ignore(self):
        self._test_lswitch_extid_update_no_exist(if_exists=True)

    def test_lswitch_no_exist_fail(self):
        self._test_lswitch_extid_update_no_exist(if_exists=False)

    def test_lswitch_extid_update(self):
        network_name = 'private'
        new_network_name = 'private-new'
        ext_ids = {ovn_const.OVN_NETWORK_NAME_EXT_ID_KEY: network_name}
        new_ext_ids = {ovn_const.OVN_NETWORK_NAME_EXT_ID_KEY: new_network_name}
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': ext_ids})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            cmd = commands.LSwitchSetExternalIdCommand(
                self.ovn_api, fake_lswitch.name,
                ovn_const.OVN_NETWORK_NAME_EXT_ID_KEY,
                new_network_name,
                if_exists=True)
            cmd.run_idl(self.transaction)
            self.assertEqual(new_ext_ids, fake_lswitch.external_ids)


class TestAddLSwitchPortCommand(TestBaseCommand):

    def test_lswitch_not_found(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.AddLSwitchPortCommand(
                self.ovn_api, 'fake-lsp', 'fake-lswitch', may_exist=True)
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)
            self.transaction.insert.assert_not_called()

    def test_lswitch_port_exists(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=mock.ANY):
            cmd = commands.AddLSwitchPortCommand(
                self.ovn_api, 'fake-lsp', 'fake-lswitch', may_exist=True)
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_not_called()

    def test_lswitch_port_add_exists(self):
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            fake_lsp = fakes.FakeOvsdbRow.create_one_ovsdb_row()
            self.ovn_api._tables['Logical_Switch_Port'].rows[fake_lsp.uuid] = \
                fake_lsp
            self.transaction.insert.return_value = fake_lsp
            cmd = commands.AddLSwitchPortCommand(
                self.ovn_api, fake_lsp.name, fake_lswitch.name,
                may_exist=False)
            cmd.run_idl(self.transaction)
            # NOTE(rtheis): Mocking the transaction allows this insert
            # to succeed when it normally would fail due the duplicate name.
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Logical_Switch_Port'])

    def _test_lswitch_port_add(self, may_exist=True):
        lsp_name = 'fake-lsp'
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=[fake_lswitch, None]):
            fake_lsp = fakes.FakeOvsdbRow.create_one_ovsdb_row(
                attrs={'foo': None})
            self.transaction.insert.return_value = fake_lsp
            cmd = commands.AddLSwitchPortCommand(
                self.ovn_api, lsp_name, fake_lswitch.name,
                may_exist=may_exist, foo='bar')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Logical_Switch_Port'])
            fake_lswitch.verify.assert_called_once_with('ports')
            self.assertEqual(lsp_name, fake_lsp.name)
            self.assertEqual([fake_lsp.uuid], fake_lswitch.ports)
            self.assertEqual('bar', fake_lsp.foo)

    def test_lswitch_port_add_may_exist(self):
        self._test_lswitch_port_add(may_exist=True)

    def test_lswitch_port_add_ignore_exists(self):
        self._test_lswitch_port_add(may_exist=False)


class TestSetLSwitchPortCommand(TestBaseCommand):

    def _test_lswitch_port_update_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.SetLSwitchPortCommand(
                self.ovn_api, 'fake-lsp', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_port_no_exist_ignore(self):
        self._test_lswitch_port_update_no_exist(if_exists=True)

    def test_lswitch_port_no_exist_fail(self):
        self._test_lswitch_port_update_no_exist(if_exists=False)

    def test_lswitch_port_update(self):
        ext_ids = {ovn_const.OVN_PORT_NAME_EXT_ID_KEY: 'test'}
        new_ext_ids = {ovn_const.OVN_PORT_NAME_EXT_ID_KEY: 'test-new'}
        fake_lsp = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': ext_ids})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lsp):
            cmd = commands.SetLSwitchPortCommand(
                self.ovn_api, fake_lsp.name, if_exists=True,
                external_ids=new_ext_ids)
            cmd.run_idl(self.transaction)
            self.assertEqual(new_ext_ids, fake_lsp.external_ids)

    def _test_lswitch_port_update_del_dhcp(self, has_v4_opts, has_v6_opts):
        ext_ids = {ovn_const.OVN_PORT_NAME_EXT_ID_KEY: 'test'}
        new_ext_ids = {ovn_const.OVN_PORT_NAME_EXT_ID_KEY: 'test-new'}
        dhcp_options_tbl = self.ovn_api._tables['DHCP_Options']
        if has_v4_opts:
            fake_dhcpv4_opts = fakes.FakeOvsdbRow.create_one_ovsdb_row(
                attrs={'external_ids': {'port_id': 'fake-lsp'}})
            dhcp_options_tbl.rows[fake_dhcpv4_opts.uuid] = fake_dhcpv4_opts
        if has_v6_opts:
            fake_dhcpv6_opts = fakes.FakeOvsdbRow.create_one_ovsdb_row(
                attrs={'external_ids': {'port_id': 'fake-lsp'}})
            dhcp_options_tbl.rows[fake_dhcpv6_opts.uuid] = fake_dhcpv6_opts
        fake_lsp = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'name': 'fake-lsp',
                   'external_ids': ext_ids,
                   'dhcpv4_options': has_v4_opts and [fake_dhcpv4_opts] or [],
                   'dhcpv6_options': has_v6_opts and [fake_dhcpv6_opts] or []})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lsp):
            cmd = commands.SetLSwitchPortCommand(
                self.ovn_api, fake_lsp.name, if_exists=True,
                external_ids=new_ext_ids)
            cmd.run_idl(self.transaction)
            self.assertEqual(new_ext_ids, fake_lsp.external_ids)
            if has_v4_opts:
                fake_dhcpv4_opts.delete.assert_called_once_with()
            if has_v6_opts:
                fake_dhcpv6_opts.delete.assert_called_once_with()

    def test_lswitch_port_update_del_port_dhcpv4_options(self):
        self._test_lswitch_port_update_del_dhcp(True, False)

    def test_lswitch_port_update_del_port_dhcpv6_options(self):
        self._test_lswitch_port_update_del_dhcp(False, True)

    def test_lswitch_port_update_del_all_port_dhcp_options(self):
        self._test_lswitch_port_update_del_dhcp(True, True)


class TestDelLSwitchPortCommand(TestBaseCommand):

    def _test_lswitch_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=['fake-lsp', idlutils.RowNotFound]):
            cmd = commands.DelLSwitchPortCommand(
                self.ovn_api, 'fake-lsp', 'fake-lswitch', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_no_exist_ignore(self):
        self._test_lswitch_no_exist(if_exists=True)

    def test_lswitch_no_exist_fail(self):
        self._test_lswitch_no_exist(if_exists=False)

    def _test_lswitch_port_del_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelLSwitchPortCommand(
                self.ovn_api, 'fake-lsp', 'fake-lswitch', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_port_no_exist_ignore(self):
        self._test_lswitch_port_del_no_exist(if_exists=True)

    def test_lswitch_port_no_exist_fail(self):
        self._test_lswitch_port_del_no_exist(if_exists=False)

    def test_lswitch_port_del(self):
        fake_lsp = mock.MagicMock()
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'ports': [fake_lsp]})
        self.ovn_api._tables['Logical_Switch_Port'].rows[fake_lsp.uuid] = \
            fake_lsp
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=[fake_lsp, fake_lswitch]):
            cmd = commands.DelLSwitchPortCommand(
                self.ovn_api, fake_lsp.name, fake_lswitch.name, if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lswitch.verify.assert_called_once_with('ports')
            fake_lsp.delete.assert_called_once_with()
            self.assertEqual([], fake_lswitch.ports)


class TestAddLRouterCommand(TestBaseCommand):

    def test_lrouter_exists(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=mock.ANY):
            cmd = commands.AddLRouterCommand(
                self.ovn_api, 'fake-lrouter', may_exist=True,
                a='1', b='2')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_not_called()

    def test_lrouter_add_exists(self):
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api._tables['Logical_Router'].rows[fake_lrouter.uuid] = \
            fake_lrouter
        self.transaction.insert.return_value = fake_lrouter
        cmd = commands.AddLRouterCommand(
            self.ovn_api, fake_lrouter.name, may_exist=False)
        cmd.run_idl(self.transaction)
        # NOTE(rtheis): Mocking the transaction allows this insert
        # to succeed when it normally would fail due the duplicate name.
        self.transaction.insert.assert_called_once_with(
            self.ovn_api._tables['Logical_Router'])

    def _test_lrouter_add(self, may_exist=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=None):
            fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row()
            self.transaction.insert.return_value = fake_lrouter
            cmd = commands.AddLRouterCommand(
                self.ovn_api, 'fake-lrouter', may_exist=may_exist,
                a='1', b='2')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Logical_Router'])
            self.assertEqual('fake-lrouter', fake_lrouter.name)
            self.assertEqual('1', fake_lrouter.a)
            self.assertEqual('2', fake_lrouter.b)

    def test_lrouter_add_may_exist(self):
        self._test_lrouter_add(may_exist=True)

    def test_lrouter_add_ignore_exists(self):
        self._test_lrouter_add(may_exist=False)


class TestUpdateLRouterCommand(TestBaseCommand):

    def _test_lrouter_update_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.UpdateLRouterCommand(
                self.ovn_api, 'fake-lrouter', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lrouter_no_exist_ignore(self):
        self._test_lrouter_update_no_exist(if_exists=True)

    def test_lrouter_no_exist_fail(self):
        self._test_lrouter_update_no_exist(if_exists=False)

    def test_lrouter_update(self):
        ext_ids = {ovn_const.OVN_ROUTER_NAME_EXT_ID_KEY: 'richard'}
        new_ext_ids = {ovn_const.OVN_ROUTER_NAME_EXT_ID_KEY: 'richard-new'}
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': ext_ids})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lrouter):
            cmd = commands.UpdateLRouterCommand(
                self.ovn_api, fake_lrouter.name, if_exists=True,
                external_ids=new_ext_ids)
            cmd.run_idl(self.transaction)
            self.assertEqual(new_ext_ids, fake_lrouter.external_ids)


class TestDelLRouterCommand(TestBaseCommand):

    def _test_lrouter_del_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelLRouterCommand(
                self.ovn_api, 'fake-lrouter', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lrouter_no_exist_ignore(self):
        self._test_lrouter_del_no_exist(if_exists=True)

    def test_lrouter_no_exist_fail(self):
        self._test_lrouter_del_no_exist(if_exists=False)

    def test_lrouter_del(self):
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api._tables['Logical_Router'].rows[fake_lrouter.uuid] = \
            fake_lrouter
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lrouter):
            cmd = commands.DelLRouterCommand(
                self.ovn_api, fake_lrouter.name, if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lrouter.delete.assert_called_once_with()


class TestAddLRouterPortCommand(TestBaseCommand):

    def test_lrouter_not_found(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.AddLRouterPortCommand(
                self.ovn_api, 'fake-lrp', 'fake-lrouter')
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)
            self.transaction.insert.assert_not_called()

    def test_lrouter_port_exists(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=mock.ANY):
            cmd = commands.AddLRouterPortCommand(
                self.ovn_api, 'fake-lrp', 'fake-lrouter')
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)
            self.transaction.insert.assert_not_called()

    def test_lrouter_port_add(self):
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=[fake_lrouter,
                                            idlutils.RowNotFound]):
            fake_lrp = fakes.FakeOvsdbRow.create_one_ovsdb_row(
                attrs={'foo': None})
            self.transaction.insert.return_value = fake_lrp
            cmd = commands.AddLRouterPortCommand(
                self.ovn_api, 'fake-lrp', fake_lrouter.name, foo='bar')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Logical_Router_Port'])
            self.assertEqual('fake-lrp', fake_lrp.name)
            fake_lrouter.verify.assert_called_once_with('ports')
            self.assertEqual([fake_lrp], fake_lrouter.ports)
            self.assertEqual('bar', fake_lrp.foo)


class TestUpdateLRouterPortCommand(TestBaseCommand):

    def _test_lrouter_port_update_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.UpdateLRouterPortCommand(
                self.ovn_api, 'fake-lrp', 'fake-lrouter', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lrouter_port_no_exist_ignore(self):
        self._test_lrouter_port_update_no_exist(if_exists=True)

    def test_lrouter_port_no_exist_fail(self):
        self._test_lrouter_port_update_no_exist(if_exists=False)

    def test_lrouter_port_update(self):
        old_networks = []
        new_networks = ['10.1.0.0/24']
        fake_lrp = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'networks': old_networks})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lrp):
            cmd = commands.UpdateLRouterPortCommand(
                self.ovn_api, fake_lrp.name, 'fake-lrouter', if_exists=True,
                networks=new_networks)
            cmd.run_idl(self.transaction)
            self.assertEqual(new_networks, fake_lrp.networks)


class TestDelLRouterPortCommand(TestBaseCommand):

    def _test_lrouter_port_del_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelLRouterPortCommand(
                self.ovn_api, 'fake-lrp', 'fake-lrouter', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lrouter_port_no_exist_ignore(self):
        self._test_lrouter_port_del_no_exist(if_exists=True)

    def test_lrouter_port_no_exist_fail(self):
        self._test_lrouter_port_del_no_exist(if_exists=False)

    def test_lrouter_no_exist(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=[mock.ANY, idlutils.RowNotFound]):
            cmd = commands.DelLRouterPortCommand(
                self.ovn_api, 'fake-lrp', 'fake-lrouter', if_exists=True)
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lrouter_port_del(self):
        fake_lrp = mock.MagicMock()
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'ports': [fake_lrp]})
        self.ovn_api._tables['Logical_Router_Port'].rows[fake_lrp.uuid] = \
            fake_lrp
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=[fake_lrp, fake_lrouter]):
            cmd = commands.DelLRouterPortCommand(
                self.ovn_api, fake_lrp.name, fake_lrouter.name, if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lrouter.verify.assert_called_once_with('ports')
            self.assertEqual([], fake_lrouter.ports)


class TestSetLRouterPortInLSwitchPortCommand(TestBaseCommand):

    def test_lswitch_port_no_exist_fail(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.SetLRouterPortInLSwitchPortCommand(
                self.ovn_api, 'fake-lsp', 'fake-lrp')
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_port_router_update(self):
        lrp_name = 'fake-lrp'
        fake_lsp = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lsp):
            cmd = commands.SetLRouterPortInLSwitchPortCommand(
                self.ovn_api, fake_lsp.name, lrp_name)
            cmd.run_idl(self.transaction)
            self.assertEqual({'router-port': lrp_name}, fake_lsp.options)
            self.assertEqual('router', fake_lsp.type)


class TestAddACLCommand(TestBaseCommand):

    def test_lswitch_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.AddACLCommand(
                self.ovn_api, 'fake-lswitch', 'fake-lsp')
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_acl_add(self):
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            fake_acl = fakes.FakeOvsdbRow.create_one_ovsdb_row()
            self.transaction.insert.return_value = fake_acl
            cmd = commands.AddACLCommand(
                self.ovn_api, fake_lswitch.name, 'fake-lsp', match='*')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['ACL'])
            fake_lswitch.verify.assert_called_once_with('acls')
            self.assertEqual([fake_acl.uuid], fake_lswitch.acls)
            self.assertEqual({'neutron:lport': 'fake-lsp'},
                             fake_acl.external_ids)
            self.assertEqual('*', fake_acl.match)


class TestDelACLCommand(TestBaseCommand):

    def _test_lswitch_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelACLCommand(
                self.ovn_api, 'fake-lswitch', 'fake-lsp',
                if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lswitch_no_exist_ignore(self):
        self._test_lswitch_no_exist(if_exists=True)

    def test_lswitch_no_exist_fail(self):
        self._test_lswitch_no_exist(if_exists=False)

    def test_acl_del(self):
        fake_lsp_name = 'fake-lsp'
        fake_acl_del = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': {'neutron:lport': fake_lsp_name}})
        fake_acl_save = mock.ANY
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'acls': [fake_acl_del, fake_acl_save]})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            cmd = commands.DelACLCommand(
                self.ovn_api, fake_lswitch.name, fake_lsp_name,
                if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lswitch.verify.assert_called_once_with('acls')
            self.assertEqual([fake_acl_save], fake_lswitch.acls)


class TestUpdateACLsCommand(TestBaseCommand):

    def test_lswitch_no_exist(self):
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api.get_acls_for_lswitches.return_value = ({}, {}, {})
        cmd = commands.UpdateACLsCommand(
            self.ovn_api, [fake_lswitch.name], port_list=[],
            acl_new_values_dict={},
            need_compare=True)
        cmd.run_idl(self.transaction)
        self.transaction.insert.assert_not_called()
        fake_lswitch.verify.assert_not_called()

    def _test_acl_update_no_acls(self, need_compare):
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api.get_acls_for_lswitches.return_value = (
            {}, {}, {fake_lswitch.name: fake_lswitch})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            cmd = commands.UpdateACLsCommand(
                self.ovn_api, [fake_lswitch.name], port_list=[],
                acl_new_values_dict={},
                need_compare=need_compare)
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_not_called()
            fake_lswitch.verify.assert_not_called()

    def test_acl_update_compare_no_acls(self):
        self._test_acl_update_no_acls(need_compare=True)

    def test_acl_update_no_compare_no_acls(self):
        self._test_acl_update_no_acls(need_compare=False)

    def test_acl_update_compare_acls(self):
        fake_sg_rule = \
            fakes.FakeSecurityGroupRule.create_one_security_group_rule().info()
        fake_port = fakes.FakePort.create_one_port().info()
        fake_add_acl = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'match': 'add_acl'})
        fake_del_acl = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'match': 'del_acl'})
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'name': ovn_utils.ovn_name(fake_port['network_id']),
                   'acls': []})
        add_acl = ovn_acl.add_sg_rule_acl_for_port(
            fake_port, fake_sg_rule, 'add_acl')
        self.ovn_api.get_acls_for_lswitches.return_value = (
            {fake_port['id']: [fake_del_acl.match]},
            {fake_del_acl.match: fake_del_acl},
            {fake_lswitch.name.replace('neutron-', ''): fake_lswitch})
        cmd = commands.UpdateACLsCommand(
            self.ovn_api, [fake_port['network_id']],
            [fake_port], {fake_port['id']: [add_acl]},
            need_compare=True)
        self.transaction.insert.return_value = fake_add_acl
        cmd.run_idl(self.transaction)
        self.transaction.insert.assert_called_once_with(
            self.ovn_api._tables['ACL'])
        fake_lswitch.verify.assert_called_with('acls')
        self.assertEqual([fake_add_acl.uuid], fake_lswitch.acls)

    def test_acl_update_no_compare_add_acls(self):
        fake_sg_rule = \
            fakes.FakeSecurityGroupRule.create_one_security_group_rule().info()
        fake_port = fakes.FakePort.create_one_port().info()
        fake_acl = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'match': '*'})
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'name': ovn_utils.ovn_name(fake_port['network_id'])})
        add_acl = ovn_acl.add_sg_rule_acl_for_port(
            fake_port, fake_sg_rule, '*')
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            self.transaction.insert.return_value = fake_acl
            cmd = commands.UpdateACLsCommand(
                self.ovn_api, [fake_port['network_id']],
                [fake_port], {fake_port['id']: add_acl},
                need_compare=False,
                is_add_acl=True)
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['ACL'])
            fake_lswitch.verify.assert_called_once_with('acls')
            self.assertEqual([fake_acl.uuid], fake_lswitch.acls)

    def test_acl_update_no_compare_del_acls(self):
        fake_sg_rule = \
            fakes.FakeSecurityGroupRule.create_one_security_group_rule().info()
        fake_port = fakes.FakePort.create_one_port().info()
        fake_acl = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'match': '*'})
        fake_lswitch = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'name': ovn_utils.ovn_name(fake_port['network_id']),
                   'acls': [fake_acl]})
        del_acl = ovn_acl.add_sg_rule_acl_for_port(
            fake_port, fake_sg_rule, '*')
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lswitch):
            cmd = commands.UpdateACLsCommand(
                self.ovn_api, [fake_port['network_id']],
                [fake_port], {fake_port['id']: del_acl},
                need_compare=False,
                is_add_acl=False)
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_not_called()
            fake_lswitch.verify.assert_called_with('acls')
            self.assertEqual([], fake_lswitch.acls)


class TestAddStaticRouteCommand(TestBaseCommand):

    def test_lrouter_not_found(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.AddStaticRouteCommand(self.ovn_api, 'fake-lrouter')
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)
            self.transaction.insert.assert_not_called()

    def test_static_route_add(self):
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lrouter):
            fake_static_route = fakes.FakeOvsdbRow.create_one_ovsdb_row()
            self.transaction.insert.return_value = fake_static_route
            cmd = commands.AddStaticRouteCommand(
                self.ovn_api, fake_lrouter.name,
                nexthop='40.0.0.100',
                ip_prefix='30.0.0.0/24')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Logical_Router_Static_Route'])
            self.assertEqual('40.0.0.100', fake_static_route.nexthop)
            self.assertEqual('30.0.0.0/24', fake_static_route.ip_prefix)
            fake_lrouter.verify.assert_called_once_with('static_routes')
            self.assertEqual([fake_static_route.uuid],
                             fake_lrouter.static_routes)


class TestDelStaticRouteCommand(TestBaseCommand):

    def _test_lrouter_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelStaticRouteCommand(
                self.ovn_api, 'fake-lrouter',
                '30.0.0.0/24', '40.0.0.100',
                if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_lrouter_no_exist_ignore(self):
        self._test_lrouter_no_exist(if_exists=True)

    def test_lrouter_no_exist_fail(self):
        self._test_lrouter_no_exist(if_exists=False)

    def test_static_route_del(self):
        fake_static_route = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'ip_prefix': '50.0.0.0/24', 'nexthop': '40.0.0.101'})
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'static_routes': [fake_static_route]})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lrouter):
            cmd = commands.DelStaticRouteCommand(
                self.ovn_api, fake_lrouter.name,
                fake_static_route.ip_prefix, fake_static_route.nexthop,
                if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lrouter.verify.assert_called_once_with('static_routes')
            self.assertEqual([], fake_lrouter.static_routes)

    def test_static_route_del_not_found(self):
        fake_static_route1 = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'ip_prefix': '50.0.0.0/24', 'nexthop': '40.0.0.101'})
        fake_static_route2 = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'ip_prefix': '60.0.0.0/24', 'nexthop': '70.0.0.101'})
        fake_lrouter = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'static_routes': [fake_static_route2]})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_lrouter):
            cmd = commands.DelStaticRouteCommand(
                self.ovn_api, fake_lrouter.name,
                fake_static_route1.ip_prefix, fake_static_route1.nexthop,
                if_exists=True)
            cmd.run_idl(self.transaction)
            fake_lrouter.verify.assert_not_called()
            self.assertEqual([mock.ANY], fake_lrouter.static_routes)


class TestAddAddrSetCommand(TestBaseCommand):

    def test_addrset_exists(self):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=mock.ANY):
            cmd = commands.AddAddrSetCommand(
                self.ovn_api, 'fake-addrset', may_exist=True)
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_not_called()

    def test_addrset_add_exists(self):
        fake_addrset = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api._tables['Address_Set'].rows[fake_addrset.uuid] = \
            fake_addrset
        self.transaction.insert.return_value = fake_addrset
        cmd = commands.AddAddrSetCommand(
            self.ovn_api, fake_addrset.name, may_exist=False)
        cmd.run_idl(self.transaction)
        # NOTE(rtheis): Mocking the transaction allows this insert
        # to succeed when it normally would fail due the duplicate name.
        self.transaction.insert.assert_called_once_with(
            self.ovn_api._tables['Address_Set'])

    def _test_addrset_add(self, may_exist=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=None):
            fake_addrset = fakes.FakeOvsdbRow.create_one_ovsdb_row(
                attrs={'foo': ''})
            self.transaction.insert.return_value = fake_addrset
            cmd = commands.AddAddrSetCommand(
                self.ovn_api, 'fake-addrset', may_exist=may_exist,
                foo='bar')
            cmd.run_idl(self.transaction)
            self.transaction.insert.assert_called_once_with(
                self.ovn_api._tables['Address_Set'])
            self.assertEqual('fake-addrset', fake_addrset.name)
            self.assertEqual('bar', fake_addrset.foo)

    def test_addrset_add_may_exist(self):
        self._test_addrset_add(may_exist=True)

    def test_addrset_add_ignore_exists(self):
        self._test_addrset_add(may_exist=False)


class TestDelAddrSetCommand(TestBaseCommand):

    def _test_addrset_del_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.DelAddrSetCommand(
                self.ovn_api, 'fake-addrset', if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_addrset_no_exist_ignore(self):
        self._test_addrset_del_no_exist(if_exists=True)

    def test_addrset_no_exist_fail(self):
        self._test_addrset_del_no_exist(if_exists=False)

    def test_addrset_del(self):
        fake_addrset = fakes.FakeOvsdbRow.create_one_ovsdb_row()
        self.ovn_api._tables['Address_Set'].rows[fake_addrset.uuid] = \
            fake_addrset
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_addrset):
            cmd = commands.DelAddrSetCommand(
                self.ovn_api, fake_addrset.name, if_exists=True)
            cmd.run_idl(self.transaction)
            fake_addrset.delete.assert_called_once_with()


class TestUpdateAddrSetCommand(TestBaseCommand):

    def _test_addrset_update_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.UpdateAddrSetCommand(
                self.ovn_api, 'fake-addrset',
                addrs_add=[], addrs_remove=[],
                if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_addrset_no_exist_ignore(self):
        self._test_addrset_update_no_exist(if_exists=True)

    def test_addrset_no_exist_fail(self):
        self._test_addrset_update_no_exist(if_exists=False)

    def _test_addrset_update(self, addrs_add=None, addrs_del=None):
        save_address = '10.0.0.1'
        initial_addresses = [save_address]
        final_addresses = [save_address]
        if addrs_add:
            for addr_add in addrs_add:
                final_addresses.append(addr_add)
        if addrs_del:
            for addr_del in addrs_del:
                initial_addresses.append(addr_del)
        fake_addrset = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'addresses': initial_addresses})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_addrset):
            cmd = commands.UpdateAddrSetCommand(
                self.ovn_api, fake_addrset.name,
                addrs_add=addrs_add, addrs_remove=addrs_del,
                if_exists=True)
            cmd.run_idl(self.transaction)
            fake_addrset.verify.assert_called_once_with('addresses')
            self.assertEqual(final_addresses, fake_addrset.addresses)

    def test_addrset_update_add(self):
        self._test_addrset_update(addrs_add=['10.0.0.4'])

    def test_addrset_update_del(self):
        self._test_addrset_update(addrs_del=['10.0.0.2'])


class TestUpdateAddrSetExtIdsCommand(TestBaseCommand):
    def setUp(self):
        super(TestUpdateAddrSetExtIdsCommand, self).setUp()
        self.ext_ids = {ovn_const.OVN_SG_NAME_EXT_ID_KEY: 'default'}

    def _test_addrset_extids_update_no_exist(self, if_exists=True):
        with mock.patch.object(idlutils, 'row_by_value',
                               side_effect=idlutils.RowNotFound):
            cmd = commands.UpdateAddrSetExtIdsCommand(
                self.ovn_api, 'fake-addrset', self.ext_ids,
                if_exists=if_exists)
            if if_exists:
                cmd.run_idl(self.transaction)
            else:
                self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_addrset_no_exist_ignore(self):
        self._test_addrset_extids_update_no_exist(if_exists=True)

    def test_addrset_no_exist_fail(self):
        self._test_addrset_extids_update_no_exist(if_exists=False)

    def test_addrset_extids_update(self):
        new_ext_ids = {ovn_const.OVN_SG_NAME_EXT_ID_KEY: 'default-new'}
        fake_addrset = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': self.ext_ids})
        with mock.patch.object(idlutils, 'row_by_value',
                               return_value=fake_addrset):
            cmd = commands.UpdateAddrSetExtIdsCommand(
                self.ovn_api, fake_addrset.name,
                new_ext_ids, if_exists=True)
            cmd.run_idl(self.transaction)
            self.assertEqual(new_ext_ids, fake_addrset.external_ids)


class TestAddDHCPOptionsCommand(TestBaseCommand):

    def test_dhcp_options_exists(self):
        fake_ext_ids = {'subnet_id': 'fake-subnet-id',
                        'port_id': 'fake-port-id'}
        fake_dhcp_options = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': fake_ext_ids})
        self.ovn_api._tables['DHCP_Options'].rows[fake_dhcp_options.uuid] = \
            fake_dhcp_options
        cmd = commands.AddDHCPOptionsCommand(
            self.ovn_api, fake_ext_ids['subnet_id'], fake_ext_ids['port_id'],
            may_exists=True, external_ids=fake_ext_ids)
        cmd.run_idl(self.transaction)
        self.transaction.insert.assert_not_called()
        self.assertEqual(fake_ext_ids, fake_dhcp_options.external_ids)

    def _test_dhcp_options_add(self, may_exists=True):
        fake_subnet_id = 'fake-subnet-id-' + str(may_exists)
        fake_port_id = 'fake-port-id-' + str(may_exists)
        fake_ext_ids1 = {'subnet_id': fake_subnet_id, 'port_id': fake_port_id}
        fake_dhcp_options1 = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': fake_ext_ids1})
        self.ovn_api._tables['DHCP_Options'].rows[fake_dhcp_options1.uuid] = \
            fake_dhcp_options1
        fake_ext_ids2 = {'subnet_id': fake_subnet_id}
        fake_dhcp_options2 = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': fake_ext_ids2})
        fake_dhcp_options3 = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': {'subnet_id': 'nomatch'}})
        self.ovn_api._tables['DHCP_Options'].rows[fake_dhcp_options3.uuid] = \
            fake_dhcp_options3
        self.transaction.insert.return_value = fake_dhcp_options2
        cmd = commands.AddDHCPOptionsCommand(
            self.ovn_api, fake_ext_ids2['subnet_id'], may_exists=may_exists,
            external_ids=fake_ext_ids2)
        cmd.run_idl(self.transaction)
        self.transaction.insert.assert_called_once_with(
            self.ovn_api._tables['DHCP_Options'])
        self.assertEqual(fake_ext_ids2, fake_dhcp_options2.external_ids)

    def test_dhcp_options_add_may_exist(self):
        self._test_dhcp_options_add(may_exists=True)

    def test_dhcp_options_add_ignore_exists(self):
        self._test_dhcp_options_add(may_exists=False)


class TestDelDHCPOptionsCommand(TestBaseCommand):

    def _test_dhcp_options_del_no_exist(self, if_exists=True):
        cmd = commands.DelDHCPOptionsCommand(
            self.ovn_api, 'fake-dhcp-options', if_exists=if_exists)
        if if_exists:
            cmd.run_idl(self.transaction)
        else:
            self.assertRaises(RuntimeError, cmd.run_idl, self.transaction)

    def test_dhcp_options_no_exist_ignore(self):
        self._test_dhcp_options_del_no_exist(if_exists=True)

    def test_dhcp_options_no_exist_fail(self):
        self._test_dhcp_options_del_no_exist(if_exists=False)

    def test_dhcp_options_del(self):
        fake_dhcp_options = fakes.FakeOvsdbRow.create_one_ovsdb_row(
            attrs={'external_ids': {'subnet_id': 'fake-subnet-id'}})
        self.ovn_api._tables['DHCP_Options'].rows[fake_dhcp_options.uuid] = \
            fake_dhcp_options
        cmd = commands.DelDHCPOptionsCommand(
            self.ovn_api, fake_dhcp_options.uuid, if_exists=True)
        cmd.run_idl(self.transaction)
        fake_dhcp_options.delete.assert_called_once_with()
