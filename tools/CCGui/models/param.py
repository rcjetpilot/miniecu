# -*- python -*-

import logging
import threading
from utils import singleton, Signal
from commmgr import CommManager

log = logging.getLogger(__name__)


class Parameter(object):
    def __init__(self, param_id, param_index, value):
        self.param_id = param_id
        self.param_index = param_index
        self._value = value
        self._init_type = type(value)
        self._changed = False

    def __repr__(self):
        return "<{} {} #{} {}({}){}>".format(
            Parameter.__name__, self.param_id, self.param_index,
            self._init_type.__name__, self._value,
            '*' if self._changed else ''
        )

    @property
    def is_changed(self):
        return self._changed

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, value):
        # only set value it it pass validator (type constructor)
        try:
            prev = self._value
            self._value = self._init_type(value)
            self._changed = self._value != prev
        except ValueError as ex:
            log.error("Set: %s: %s", self.param_id, repr(ex))

    def validate(self, value):
        # TODO: more paranoic validate process
        try:
            self._init_type(value)
        except ValueError:
            return False

        return True


@singleton
class ParamManager(object):
    def __init__(self):
        self.parameters = {}
        self.missing_ids = set()
        self._event = threading.Event()
        self.sig_changed = Signal()
        CommManager().register_model(self)

    @property
    def changed(self):
        return [p for p in self.parameters.values() if p.is_changed]

    def clear(self):
        self.parameters.clear()
        self.sig_changed.emit()

    def update_param(self, param_id, param_index, param_count, value):
        if len(self.missing_ids) == 0:
            self.missing_ids.update(range(param_count))

        p = self.parameters.get(param_id)
        if p:
            p._value = value
            p._changed = False
            log.debug("Update: %s: %s", p.param_id, p.value)
        else:
            self.parameters[param_id] = Parameter(param_id, param_index, value)
            log.debug("Add: %s: %s", param_id, value)

        self.missing_ids.discard(param_index)
        if len(self.missing_ids) == 0:
            log.debug("Retrive done")
            self._event.set()

    def retrieve_all(self):
        self.missing_ids = set()
        self._event.clear()

        # request all
        CommManager().param_request()
        self._event.wait(10.0)

        # not nesessary: try to request missing params
        if len(self.missing_ids) > 0:
            log.warn("Missing %d parameters, trying to request.", len(self.missing_ids))
            self._event.clear()
            for idx in self.missing_ids:
                CommManager().param_request(param_index=idx)

            self._event.wait(10.0)

        if len(self.missing_ids):
            log.error("Missing %d parameters", len(self.missing_ids))

        self.sig_changed.emit()
        return len(self.missing_ids) == 0

    def sync(self):
        to_sync = self.changed
        if len(to_sync) == 0:
            log.info("Nothing to sync")
            self.sig_changed.emit()
            return True

        self.missing_ids = set((p.param_index for p in to_sync))
        self._event.clear()
        for p in to_sync:
            CommManager().param_set(p.param_id, p.value)

        self._event.wait(10.0)
        if len(self.missing_ids):
            log.error("Not synced %d parameters", len(self.missing_ids))

        self.sig_changed.emit()
        return len(self.missing_ids) == 0

# initialize manager at module loading
ParamManager()
