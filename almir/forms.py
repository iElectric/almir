import colander
from deform_bootstrap.widget import DateTimeInputWidget, ChosenSingleWidget

from almir.models import TYPES, VOLUME_STATUS_SEVERITY

job_states = (
    ('finished+running', 'Finished + Running'),
    ('scheduled', 'Scheduled'),
    ('disabled', 'Disabled'),
)


def deferred_widget_factory(values_name):
    @colander.deferred
    def deferred_widget(node, kw):
        widget = kw.get('widget', ChosenSingleWidget)
        values = kw.get(values_name, [])
        return widget(values=values)
    return deferred_widget


class JobSchema(colander.MappingSchema):
    state = colander.SchemaNode(colander.String(),
                                name='state',
                                widget=ChosenSingleWidget(values=job_states),
                                missing=colander.null,
                                default="finished+running")
    type = colander.SchemaNode(colander.String(),
                               widget=ChosenSingleWidget(values=[('', '---')] + TYPES.items()),
                               missing=colander.null)
    status = colander.SchemaNode(colander.String(),
                                missing=colander.null,
                                 widget=deferred_widget_factory('status_values'))


class MediaSchema(colander.MappingSchema):
    status = colander.SchemaNode(colander.String(),
                                 widget=ChosenSingleWidget(values=[('', '---')] + zip(VOLUME_STATUS_SEVERITY.keys(), VOLUME_STATUS_SEVERITY.keys())),
                                 missing=colander.null)
    storage = colander.SchemaNode(colander.Integer(),
                                  missing=colander.null,
                                  widget=deferred_widget_factory('storage_values'))
    pool = colander.SchemaNode(colander.Integer(),
                               missing=colander.null,
                               widget=deferred_widget_factory('pool_values'))


class LogSchema(colander.MappingSchema):
    from_time = colander.SchemaNode(colander.DateTime(),
                                    description=u"NOTE: time should be in form of HH:MM:SS",
                                    missing=colander.null,
                                    widget=DateTimeInputWidget())
    to_time = colander.SchemaNode(colander.DateTime(),
                                  description=u"NOTE: time should be in form of HH:MM:SS",
                                  missing=colander.null,
                                  widget=DateTimeInputWidget())

# TODO: upstream: fix whitespace in .form-actions div
