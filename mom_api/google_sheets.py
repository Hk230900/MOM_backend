import json
import logging
import threading
import requests
from django.utils import timezone
from google.oauth2 import service_account
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

def perform_sync(integration, data):
    """
    Executes the sync operation synchronously. Raises exceptions on failure.
    """
    if integration.integration_type == 'webhook':
        if not integration.webhook_url:
            raise ValueError("No webhook URL configured for the integration.")
            
        headers = {'Content-Type': 'application/json'}
        response = requests.post(integration.webhook_url, json=data, headers=headers, timeout=15)
        
        if response.status_code not in (200, 201):
            raise Exception(f"Webhook returned status code {response.status_code}: {response.text}")
            
        try:
            res_data = response.json()
            if isinstance(res_data, dict) and res_data.get("status") == "error":
                raise Exception(f"Apps Script Error: {res_data.get('message')}")
        except json.JSONDecodeError:
            pass

    elif integration.integration_type == 'service_account':
        if not integration.spreadsheet_id:
            raise ValueError("No spreadsheet ID configured for the integration.")
            
        creds_json = integration.credentials_json
        if not creds_json:
            import os
            creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
            
        if not creds_json:
            raise ValueError("No Service Account credentials JSON provided.")
            
        try:
            creds_dict = json.loads(creds_json)
            credentials = service_account.Credentials.from_service_account_info(
                creds_dict,
                scopes=["https://www.googleapis.com/auth/spreadsheets"]
            )
        except Exception as e:
            raise ValueError(f"Invalid Service Account JSON format: {str(e)}")
            
        service = build("sheets", "v4", credentials=credentials)
        spreadsheet_id = integration.spreadsheet_id
        sheet_name = integration.sheet_name or "Meetings"
        
        # Ensure sheet exists / retrieve data
        range_to_search = f"'{sheet_name}'!A:A"
        try:
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_to_search
            ).execute()
            rows = result.get("values", [])
        except Exception as e:
            logger.warning(f"Error reading range or sheet. Initializing sheet... {e}")
            headers = ["Date", "Day", "Meeting Title", "Mom details", "Assigned Task", "Per task status", "Meeting ID", "Task Index"]
            try:
                service.spreadsheets().values().append(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{sheet_name}'!A1",
                    valueInputOption="RAW",
                    body={"values": [headers]}
                ).execute()
                rows = [["Date"]]
            except Exception as init_err:
                raise Exception(f"Could not initialize sheet '{sheet_name}'. Verify sheet name and access: {str(init_err)}")
                
        meeting_id_str = str(data["meeting_id"])
        
        # Read the entire table to locate rows
        range_all = f"'{sheet_name}'!A:H"
        result_all = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_all
        ).execute()
        all_rows = result_all.get("values", [])
        
        # Find row indices (1-indexed for Sheets) matching meeting ID
        matching_row_indices = []
        for idx, row in enumerate(all_rows):
            if len(row) > 6 and str(row[6]) == meeting_id_str:
                matching_row_indices.append(idx + 1)
                
        # Build new rows list
        new_rows = []
        action_items = data.get("action_items", [])
        if not action_items:
            new_rows.append([
                data["date"],
                data["day"],
                data["title"],
                data["mom_details"],
                "", # Assigned Task
                "", # Per task status
                data["meeting_id"],
                -1
            ])
        else:
            for idx, item in enumerate(action_items):
                task_desc = item.get("task", "")
                if item.get("assignee"):
                    task_desc += f" ({item['assignee']})"
                task_status = "Completed" if item.get("completed") else "Pending"
                new_rows.append([
                    data["date"],
                    data["day"],
                    data["title"],
                    data["mom_details"],
                    task_desc,
                    task_status,
                    data["meeting_id"],
                    idx
                ])
                
        N = len(matching_row_indices)
        M = len(new_rows)
        
        # 1. Update/Overwrite existing matching rows
        for i in range(min(N, M)):
            row_num = matching_row_indices[i]
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A{row_num}:H{row_num}",
                valueInputOption="RAW",
                body={"values": [new_rows[i]]}
            ).execute()
            
        # 2. If we have more new rows than old, append them
        if M > N:
            extra_rows = new_rows[N:]
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"'{sheet_name}'!A:H",
                valueInputOption="RAW",
                body={"values": extra_rows}
            ).execute()
            
        # 3. If we have fewer new rows than old, clear the extra old rows
        elif N > M:
            for i in range(M, N):
                row_num = matching_row_indices[i]
                service.spreadsheets().values().clear(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{sheet_name}'!A{row_num}:H{row_num}"
                ).execute()

def sync_meeting_to_google_sheet(meeting):
    """
    Asynchronously syncs a meeting to Google Sheets if an active integration exists for its project.
    """
    if not meeting.project:
        return
        
    from .models import GoogleSheetIntegration
    integration = GoogleSheetIntegration.objects.filter(project=meeting.project, is_active=True).first()
    
    if not integration:
        return
        
    day_name = meeting.date.strftime("%A")
    
    formatted_actions = []
    if meeting.action_items and isinstance(meeting.action_items, list):
        for item in meeting.action_items:
            task_text = item.get("text", "")
            assignee_name = item.get("assignee_name", "")
            if not assignee_name and item.get("assignees"):
                assignee_name = ", ".join([a.get("name", "") for a in item["assignees"]])
            
            formatted_actions.append({
                "task": task_text,
                "assignee": assignee_name,
                "completed": item.get("completed", False)
            })
            
    meeting_data = {
        "meeting_id": meeting.id,
        "title": meeting.title,
        "date": meeting.date.strftime("%Y-%m-%d"),
        "day": day_name,
        "mom_details": meeting.minutes or "",
        "action_items": formatted_actions,
        "last_updated": timezone.localtime(meeting.updated_at).strftime("%Y-%m-%d %H:%M:%S")
    }
    
    def run_sync():
        try:
            perform_sync(integration, meeting_data)
            integration.last_sync_status = 'Success'
            integration.last_sync_error = None
        except Exception as e:
            logger.error(f"Error syncing meeting {meeting.id} to Google Sheets: {e}")
            integration.last_sync_status = 'Failed'
            integration.last_sync_error = str(e)
        finally:
            integration.last_sync_at = timezone.now()
            integration.save(update_fields=['last_sync_status', 'last_sync_error', 'last_sync_at'])
            
    threading.Thread(target=run_sync, daemon=True).start()
