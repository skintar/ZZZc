import json

def handler(event, context):
    """Простейшая lambda функция для Vercel"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'status': 'success',
            'message': 'Simple Vercel function working!',
            'event': str(event)[:200] if event else 'No event'
        })
    }