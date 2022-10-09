


from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import numpy as np

import httplib2
import logging


import socket

socket.setdefaulttimeout(600)


class GoogleSheetsClient:
    def __init__(self, credentials):
        if credentials:
            http = httplib2.Http(timeout=600)

            self.credentials = self.load_credentials(credentials)
            self.drive_service = build("drive", "v3", credentials=self.credentials)
            self.sheets_service = build("sheets", "v4", credentials=self.credentials)
        else:
            logging.warning("No Google Cloud credentials provided")

    @staticmethod
    def load_credentials(credentials):
        return Credentials.from_service_account_info(
            credentials,
            scopes=[
                "https://www.googleapis.com/auth/drive",
                "https://www.googleapis.com/auth/spreadsheets",
            ],  # Modified,
        )

    def get_sheets_names(self, spreadsheet_id):
        sheet_metadata = (
            self.sheets_service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id)
            .execute()
        )
        sheets = sheet_metadata.get("sheets", "")
        title = sheets[0].get("properties", {}).get("title", "Sheet1")
        return title

    def create_spreadsheet(self, name, tab_name=None):
        file_metadata = (
            self.drive_service.files()
            .create(
                body={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.spreadsheet",
                }
            )
            .execute()
        )
        sheet_id = file_metadata.get("id")
        if tab_name:
            self.edit_tab_name(sheet_id, tab_id=0, tab_name=tab_name)
        return file_metadata

    def grant_permissions(self, file_id, role, email):
        results = (
            self.drive_service.permissions()
            .create(
                fileId=file_id,
                sendNotificationEmail=False,
                body={"type": "user", "role": role, "emailAddress": email},
            )
            .execute()
        )
        return results


    def get_sheets_df(self, sheet_id, range_name):
        sheet = self.sheets_service.spreadsheets()

        result = sheet.values().get(spreadsheetId=sheet_id, range=range_name).execute()

        values = result.get("values", [])
        return values

    def edit_tab_name(self, sheet_id, tab_id, tab_name):
        body = {
            "requests": {
                "updateSheetProperties": {
                    "properties": {"sheetId": tab_id, "title": tab_name},
                    "fields": "title",
                }
            }
        }
        response = (
            self.sheets_service.spreadsheets()
            .batchUpdate(spreadsheetId=sheet_id, body=body)
            .execute()
        )
        return response

    def get_tabs_metadata(self, sheets_id):
        sheets_metadata = (
            self.sheets_service.spreadsheets().get(spreadsheetId=sheets_id).execute()
        )
        tabs = sheets_metadata.get("sheets", [{}])
        tabs_metadata = [
            {
                "tab_id": tab.get("properties", {}).get("sheetId"),
                "tab_name": tab.get("properties", {}).get("title"),
            }
            for tab in tabs
        ]
        return tabs_metadata
    
    def delete_columns(self, spreadsheet_id, tab_name, start_index, end_index):
        tabs = self.get_tabs_metadata(spreadsheet_id)
        tab_id = [tab["tab_id"] for tab in tabs if tab["tab_name"] == tab_name]
        if not tab_id:
            raise Exception("Tab name does not exist")
        else:
            tab_id = tab_id[0]
        body = {
            "requests": [
                {
                    "deleteDimension": {
                        "range": {
                            "sheetId": tab_id,
                            "dimension": "COLUMNS",
                            "startIndex": start_index,
                            "endIndex": end_index,
                        }
                    }
                }
            ]
        }
        response = (
            self.sheets_service.spreadsheets()
            .batchUpdate(spreadsheetId=spreadsheet_id, body=body)
            .execute()
        )
        return response

    def upload_dataframe_to_spreadsheet(
        self,
        df,
        sheets_id,
        infer_types=False,
        tab_name="Sheet1",
        start_cell="B1",
        add_columns=True,
    ):
        def df_to_sheets(df):
            columns = [np.array(df.columns)]
            values = df.values.tolist()
            rows = np.concatenate((columns, values)).tolist()
            return rows

        value_input_option = "USER_ENTERED" if infer_types else "RAW"
        converted_df = df_to_sheets(df)
        body = {"values": converted_df if add_columns else converted_df[1:]}

        if add_columns:
            _, n_columns = df.shape
            end_index = 26
            # if n_columns < end_index:
            # start_index = n_columns
            # self.delete_columns(sheets_id, tab_name, start_index, end_index)
        # < /Make this prettier >
        result = (
            self.sheets_service.spreadsheets()
            .values()
            .append(
                spreadsheetId=sheets_id,
                valueInputOption=value_input_option,
                body=body,
                range=f"{tab_name}!{start_cell}",
            )
            .execute()
        )
        return result

