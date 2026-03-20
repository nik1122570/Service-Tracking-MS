from service_app.service_tracking.doctype.eah_job_card.eah_job_card import (
    validate_purchase_order_job_card_integrity,
)
from service_app.service_tracking.doctype.tyre_request.tyre_request import (
    validate_purchase_order_tyre_request_integrity,
)


def validate_purchase_order_source_integrity(doc, method=None):
    validate_purchase_order_job_card_integrity(doc, method)
    validate_purchase_order_tyre_request_integrity(doc, method)
