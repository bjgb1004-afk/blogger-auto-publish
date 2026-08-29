from googleapiclient.discovery import build

from google_auth import get_credentials


def get_service():
    return build('searchconsole', 'v1', credentials=get_credentials())


def get_query_performance(site_url, start_date, end_date, dimensions=None, row_limit=100):
    body = {
        'startDate': start_date,
        'endDate': end_date,
        'dimensions': dimensions or ['query'],
        'rowLimit': row_limit,
    }
    resp = get_service().searchanalytics().query(siteUrl=site_url, body=body).execute()
    return resp.get('rows', [])
