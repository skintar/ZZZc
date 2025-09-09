def handler(request):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'text/html; charset=utf-8'
        },
        'body': '''
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>🎯 TEST SUCCESS</title>
        </head>
        <body style="font-family: Arial; text-align: center; margin-top: 100px;">
            <h1 style="color: green;">✅ VERCEL РАБОТАЕТ!</h1>
            <p>Простейшая функция успешно развёрнута</p>
            <p>Время: <span id="time"></span></p>
            <script>
                document.getElementById('time').textContent = new Date().toLocaleString();
            </script>
        </body>
        </html>
        '''
    }