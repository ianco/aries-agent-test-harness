# -----------------------------------------------------------
# Behave environtment file used to hold test hooks to do
# Setup and Tear Downs at different levels
# For more info see:
# https://behave.readthedocs.io/en/latest/tutorial.html#environmental-controls
#  
# -----------------------------------------------------------
import json

def before_scenario(context, scenario):
    
    # Check if the scenario has an issue associated
    for tag in context.tags:
        if '.issue:' in tag:
            
            # Parse out the URL in the issue tag.
            l_issue_info = tag.split(":")
            s_issue_url = 'https:' + l_issue_info[2]

            #get the test id for this scenario
            for tag in context.tags:
                if tag.startswith("T"):
                    test_id = tag
                    break

            # Tell the user the scenario will fail and the URL to the issue
            print ('NOTE: Test ' + test_id + ':' + scenario.name + ', WILL FAIL due to an outstanding issue not yet resolved.')
            print ('For more information see issue details at ' + s_issue_url)
            break

    # Check if the @MultiUseInvite tag exists
    if 'MultiUseInvite' in context.tags :
        
        print ('NOTE: Test \"' + scenario.name + '\" WILL FAIL if your Agent Under Test is not started with or does not support Multi Use Invites.')

    # Check for Present Froof Feature to be able to handle the loading of schemas and credential definitions before the scenarios.
    if 'present proof' in context.feature.name or 'revocation' in context.feature.name or 'Issue Credential' in context.feature.name:
            # get the tag with "Schema_".
            for tag in context.tags:
                if 'ProofType_' in tag:
                    # Get and assign the proof type to the context
                    # tag is in format "ProofType_PROOFTYPESTRING"
                    context.proof_type = tag.split("ProofType_")[1]
                if 'DidMethod_' in tag:
                    # Get and assign the did method to the context
                    # tag is in format "@DidMethod_DIDMETHOD"
                    context.did_method = tag.split("DidMethod_")[1]
                if 'Schema_' in tag:
                    # Get and assign the scehma to the context
                    try:
                        schema_json_file = open('features/data/' + tag.lower() + '.json')
                        schema_json = json.load(schema_json_file)

                        # If this is issue credential then you can't created multiple credential defs at the same time, like Proof uses
                        # mulitple crdential types in the proof. So just set the context.schema here to be used in the issue cred test.
                        # This makes the rule that you can only have one @Schema_ tag in an issue credential test scenario. 
                        if 'Issue Credential' in context.feature.name:
                            context.schema = schema_json["schema"]
                            # Get and assign the credential definition info to the context
                            context.support_revocation = schema_json["cred_def_support_revocation"]

                        # Support multiple schemas for multiple creds in a proof request.
                        # for each schema in tags add the schema and revocation support to a dict keyed by schema name.
                        if "schema_dict" in context:
                            context.schema_dict[tag] = schema_json["schema"]
                            context.support_revocation_dict[tag] = schema_json["cred_def_support_revocation"]
                        else:
                            context.schema_dict = {tag: schema_json["schema"]}
                            context.support_revocation_dict = {tag: schema_json["cred_def_support_revocation"]}

                    except FileNotFoundError:
                        print('FileNotFoundError: features/data/' + tag.lower + '.json')
                    
                    




