# -*- coding: utf-8 -*-
from functools import partial
from pkg_resources import get_distribution
from logging import getLogger
from cornice.resource import resource
from schematics.exceptions import ModelValidationError
from openprocurement.api.utils import (error_handler, get_revision_changes,
                                       context_unpack)
from openprocurement.api.models import Revision, get_now

from openprocurement.contracting.api.traversal import factory
from openprocurement.contracting.api.models import Contract


contractingresource = partial(resource, error_handler=error_handler,
                              factory=factory)

PKG = get_distribution(__package__)
LOGGER = getLogger(PKG.project_name)


def contract_from_data(request, data, raise_error=True, create=True):
    if create:
        return Contract(data)
    return Contract


def contract_serialize(request, contract_data, fields):
    contract = request.contract_from_data(contract_data, raise_error=False)
    return dict([(i, j) for i, j in contract.serialize("view").items() if i in fields])


def save_contract(request):
    """ Save contract object to database
    :param request:
    :return: True if Ok
    """
    contract = request.validated['contract']
    patch = get_revision_changes(contract.serialize("plain"),
                                 request.validated['contract_src'])
    if patch:
        contract.revisions.append(
            Revision({'author': request.authenticated_userid,
                      'changes': patch, 'rev': contract.rev}))
        old_date_modified = contract.dateModified
        contract.dateModified = get_now()
        try:
            contract.store(request.registry.db)
        except ModelValidationError, e:  # pragma: no cover
            for i in e.message:
                request.errors.add('body', i, e.message[i])
            request.errors.status = 422
        except Exception, e:  # pragma: no cover
            request.errors.add('body', 'data', str(e))
        else:
            LOGGER.info('Saved contract {}: dateModified {} -> {}'.format(
                contract.id, old_date_modified and old_date_modified.isoformat(),
                contract.dateModified.isoformat()),
                extra=context_unpack(request, {'MESSAGE_ID': 'save_contract'},
                                     {'CONTRACT_REV': contract.rev}))
            return True
