""" Page functions for Flavor pages
"""
import attr

from navmazing import NavigateToAttribute, NavigateToSibling
from widgetastic_patternfly import (Accordion, BootstrapSwitch, BreadCrumb, Button,
                                    Dropdown, TextInput, View)

from widgetastic.widget import Text, Select

from cfme.base.ui import BaseLoggedInPage
from cfme.common import Taggable
from cfme.exceptions import FlavorNotFound, ItemNotFound
from cfme.modeling.base import BaseEntity, BaseCollection
from cfme.utils.appliance.implementations.ui import CFMENavigateStep, navigator, navigate_to
from widgetastic_manageiq import (
    BaseEntitiesView, ItemsToolBarViewSelector, SummaryTable, Text, Table, Accordion, ManageIQTree,
    PaginationPane, Search)


class FlavorView(BaseLoggedInPage):
    @property
    def in_availability_zones(self):
        return (
            self.logged_in_as_current_user and
            self.navigation.currently_selected == ['Compute', 'Clouds', 'Flavors']
        )


class FlavorToolBar(View):
    policy = Dropdown('Policy')
    download = Dropdown('Download')
    configuration = Dropdown('Configuration')
    view_selector = View.nested(ItemsToolBarViewSelector)


class FlavorEntities(BaseEntitiesView):
    table = Table("//div[@id='gtl_div']//table")
    # todo: remove table and use entities instead


class FlavorDetailsToolBar(View):
    policy = Dropdown('Policy')
    download = Button(title='Download summary in PDF format')
    configuration = Dropdown('Configuration')


class FlavorDetailsAccordion(View):
    @View.nested
    class properties(Accordion):  # noqa
        tree = ManageIQTree()

    @View.nested
    class relationships(Accordion):  # noqa
        tree = ManageIQTree()


class FlavorDetailsEntities(View):
    breadcrumb = BreadCrumb()
    title = Text('//div[@id="main-content"]//h1')
    properties = SummaryTable(title='Properties')
    relationships = SummaryTable(title='Relationships')
    smart_management = SummaryTable(title='Smart Management')


class FlavorAllView(FlavorView):
    toolbar = FlavorToolBar()
    paginator = PaginationPane()
    search = View.nested(Search)
    including_entities = View.include(FlavorEntities, use_parent=True)

    @property
    def is_displayed(self):
        return (
            self.in_availability_zones and
            self.entities.title.text == 'Flavors')


class ProviderFlavorAllView(FlavorAllView):

    @property
    def is_displayed(self):
        return (
            self.logged_in_as_current_user and
            self.navigation.currently_selected == ['Compute', 'Clouds', 'Providers'] and
            self.entities.title.text == '{} (All Flavors)'.format(self.context["object"].name)
        )


class FlavorDetailsView(FlavorView):
    @property
    def is_displayed(self):
        expected_title = '{} (Summary)'.format(self.context['object'].name)
        expected_provider = self.context['object'].provider.name
        return (
            self.in_availability_zones and
            self.entities.title.text == expected_title and
            self.entities.breadcrumb.active_location == expected_title and
            self.entities.relationships.get_text_of('Cloud Provider') == expected_provider)

    toolbar = FlavorDetailsToolBar()
    sidebar = FlavorDetailsAccordion()
    entities = FlavorDetailsEntities()


class FlavorAddEntities(View):
    breadcrumb = BreadCrumb()
    title = Text('//div[@id="main-content"]//h1')


class FlavorAddForm(View):
    """ Represents Add Flavor page """
    provider = Select(name='ems_id')
    flavor_name = TextInput(name='name')
    ram_size = TextInput(name='ram')
    vcpus = TextInput(name='vcpus')
    disk_size = TextInput(name='disk')
    swap_size = TextInput(name='swap')
    rxtx_factor = TextInput(name='rxtx_factor')
    public = BootstrapSwitch(name='is_public')
    add = Button('Add')
    cancel = Button('Cancel')


class FlavorAddView(FlavorView):
    @property
    def is_displayed(self):
        expected_title = "Add a new Flavor"
        return (
            self.in_availability_zones and
            self.entities.title.text == expected_title and
            self.entities.breadcrumb.active_location == expected_title)

    entities = View.nested(FlavorAddEntities)
    form = View.nested(FlavorAddForm)


@attr.s
class Flavor(BaseEntity, Taggable):
    """
    Flavor class to support navigation
    """
    _param_name = "Flavor"

    name = attr.ib()
    provider = attr.ib()
    ram = attr.ib(default=None)
    vcpus = attr.ib(default=None)
    disk = attr.ib(default=None)
    swap = attr.ib(default=None)
    rxtx = attr.ib(default=None)
    is_public = attr.ib(default=True)

    def delete(self, cancel=False):
        """Delete current falvor """
        view = navigate_to(self, 'Details')
        view.toolbar.configuration.item_select('Remove Flavor', handle_alert=not cancel)
        view.flash.assert_no_error()

    def refresh(self):
        """Refresh provider relationships and browser"""
        self.provider.refresh_provider_relationships()
        self.browser.refresh()

    @property
    def exists(self):
        try:
            navigate_to(self, 'Details')
            return True
        except FlavorNotFound:
            return False

    @property
    def instance_count(self):
        """ number of instances using flavor.

        Returns:
            :py:class:`int` instance count.
        """
        view = navigate_to(self, 'Details')
        return int(view.entities.relationships.get_text_of('Instances'))


@attr.s
class FlavorCollection(BaseCollection):
    ENTITY = Flavor

    def create(self, name, provider, ram, vcpus, disk, swap, rxtx, is_public=True, cancel=False):
        """Create new falvor"""
        view = navigate_to(self, 'Add')
        form_params = {'provider': provider.name,
                       'flavor_name': name,
                       'ram_size': ram,
                       'vcpus': vcpus,
                       'disk_size': disk,
                       'swap_size': swap,
                       'rxtx_factor': rxtx,
                       'public': is_public}

        view.form.fill(form_params)

        if cancel:
            view.form.cancel.click()

        else:
            view.form.add.click()

        view = self.create_view(FlavorAllView)
        view.flash.assert_no_error()
        flavor = self.instantiate(name, provider, ram, vcpus, disk, swap, rxtx, is_public)
        return flavor


@navigator.register(FlavorCollection, 'All')
class FlavorAll(CFMENavigateStep):
    VIEW = FlavorAllView
    prerequisite = NavigateToAttribute('appliance.server', 'LoggedIn')

    def step(self, *args, **kwargs):
        self.prerequisite_view.navigation.select('Compute', 'Clouds', 'Flavors')


@navigator.register(Flavor, 'Details')
class FlavorDetails(CFMENavigateStep):
    VIEW = FlavorDetailsView
    prerequisite = NavigateToAttribute('parent', 'All')

    def step(self, *args, **kwargs):
        self.prerequisite_view.toolbar.view_selector.select('List View')
        try:
            row = self.prerequisite_view.entities.get_entity(name=self.obj.name, surf_pages=True)
        except ItemNotFound:
            raise FlavorNotFound('Could not locate flavor "{}" on provider {}'
                                 .format(self.obj.name, self.obj.provider.name))
        row.click()


@navigator.register(FlavorCollection, 'Add')
class FlavorAdd(CFMENavigateStep):
    prerequisite = NavigateToSibling('All')
    VIEW = FlavorAddView

    def step(self):
        self.prerequisite_view.toolbar.configuration.item_select('Add a new Flavor')
