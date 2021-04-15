import time

def create_non_revoke_interval(timeframe):
    # timeframe containes two variables, the To and from of the non-revoked to and from parameters in the send presentation request message
    # The to and from timeframe variables are always relative to now. 
    # The to and from time is represented as a total number of seconds from Unix Epoch
    # Deconstruct the timeframe and add it to the context to be used in the request later.
    # putting timefrom here where the revoke happens just in case it is needed. It may not and could be removed from here and added to the request step.
    #
    # Timeframe examples:
    # -86400:+86400
    # now:now
    # -86400:0
    # :now (openended from)
    # now: (openended to)

    timeframe_list = timeframe.split(":")
    from_reference = timeframe_list[0]
    to_reference = timeframe_list[1]

    if (from_reference == 'now') or (from_reference == ''):
        if from_reference == 'now': from_interval = int(time.time())
        if from_reference == '': from_interval = None
        #from_interval = from_reference
    else:
        from_interval = int(from_reference) + int(time.time())

    if (to_reference == 'now') or (to_reference == ''):
        if to_reference == 'now': to_reference = int(time.time())
        to_interval = to_reference
    else:
        to_interval = int(to_reference) + int(time.time())

    return {
        "non_revoked": {
            "from": from_interval,
            "to": to_interval
        }
    }

def get_relative_timestamp_to_epoch(timestamp):
    # timestamps are always relative to now. + or - is represented in seconds from Unix Epoch.
    # Valid timestsamps are 
    #  now
    #  +###### ie +86400
    #  -###### ie -86400

    if (timestamp == 'now'):
        epoch_time = int(time.time())
    else:
        epoch_time = int(timestamp) + int(time.time())

    return epoch_time

def format_cred_proposal_by_aip_version(context, aip_version, cred_data, connection_id, filters=None):

    if aip_version == "AIP20":

        filters = amend_filters_with_runtime_data(context, filters)

        # credential_proposal = {
        #     "connection_id": connection_id,
        #     "credential_preview": {
        #         "@type": "did:sov:BzCbsNYhMrjHiqZDTUASHg;spec/issue-credential/1.0/credential-preview",
        #         "attributes": cred_data,
        #     },
        #     "filter": filters
        # }
        credential_proposal = {
            "connection_id": connection_id,
            "credential_preview": {
                "@type": "issue-credential/2.0/credential-preview",
                "attributes": cred_data,
            },
            "filter": filters
        }

    return credential_proposal

def amend_filters_with_runtime_data(context, filters):
    # This method will need comdification as new types of filters are used. Intially "indy" is used.
    if "indy" in filters:
        if "schema_issuer_did" in filters["indy"] and filters["indy"]["schema_issuer_did"] == "replace_me":
            filters["indy"]["schema_issuer_did"] = context.issuer_did_dict[context.schema['schema_name']]
        if "issuer_did" in filters["indy"] and filters["indy"]["issuer_did"] == "replace_me":
            filters["indy"]["issuer_did"] = context.issuer_did_dict[context.schema['schema_name']]
        if "cred_def_id" in filters["indy"] and filters["indy"]["cred_def_id"] == "replace_me":
            filters["indy"]["cred_def_id"] = context.issuer_credential_definition_dict[context.schema['schema_name']]["id"]
        if "schema_id" in filters["indy"] and filters["indy"]["schema_id"] == "replace_me":
            filters["indy"]["schema_id"] = context.issuer_schema_dict[context.schema['schema_name']]["id"]

    if "json-ld" in filters:
        json_ld = filters.get("json-ld")
        credential = json_ld.get("credential")
        options = json_ld.get("options")

        issuer = context.issuer_did_dict[context.schema['schema_name']]

        if "issuer" in credential:
            # "issuer": "replace_me"
            if credential.get("issuer") == "replace_me":
                credential["issuer"] = issuer
            # "issuer": { "id": "replace_me" }
            elif credential.get("issuer", {}).get("id") == "replace_me":
                credential["issuer"]["id"] = issuer
        if options.get("proofType") == "replace_me":
            options["proofType"] = context.proof_type


    return filters
