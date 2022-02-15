# Debug callback view

This functionality was created to help you understand and improve your callback code.

Through this view together with some lib of caller identification for apis, database and service we were able to extract inputs for consumer optimization.

Below we have an example of using it together with the [django debug toolbar](https://django-debug-toolbar.readthedocs.io/en/latest/).

![Django callback view utilization](../../docs/example.gif)

#### Debug callback view configuration

Basically the configuration is simple, just insert in your application's `urls` code the pointer to the debug callback view route.
```python
from django.conf import settings
if settings.DEBUG:
    urlpatterns += [
        path("debug-callback/", include("django_stomp.debug_callback_view.urls")),
    ]
```

#### How to use ?

This route is a simple `POST` type route that expects to receive some parameters to trigger the callback function.

body parameter:
* `callback_function_path`: The path to callback function to be called
* `payload_body`: payload body to be sent to de callback function
* `payload_headers`: headers to be sent to de callback function

curl example
```curl
curl --request POST \
  --url http://0.0.0.0:8000/debug-callback/debug-function/ \
  --data '{
	"callback_function_path": "path.to.the.callback.function",
	"payload_body": {
		"fake": "body"
	},
	"payload_headers": {
		"fake": "headers"
	}
}'
```

#### How to use with django-debug-toolbar ?

Configuration for the [django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/en/latest/) here.

* The first step is [install de django-debug-toolbar](https://django-debug-toolbar.readthedocs.io/en/latest/installation.html) in your app
```python
pip install django-debug-toolbar
```

* The second step is to configure the urls (Recommended only insert this rule id `DEBUG` is `True`)
```python
from django.conf import settings
if settings.DEBUG:
    urlpatterns += [
        path("debug-callback/", include("django_stomp.debug_callback_view.urls")), # django stomp callback view
        path("debug-toolbar/", include("debug_toolbar.urls")) # django debug toolbar
    ]
```

* The third step is to check the settings, these settings will include the middleware and debug apps to main settings

in your `.env`
```shell
##################
#### DEBUG LIB CONFIGURATION
DEBUG_APPS = "debug_toolbar"
DEBUG_MIDDLEWARE ="debug_toolbar.middleware.DebugToolbarMiddleware"
```

in your `setting`
```python
import os
DEBUG = True # only to developer mode never in production app
# DEBUG CONFIGURATION
if DEBUG:
    DEBUG_TOOLBAR_CONFIG = {"SHOW_TOOLBAR_CALLBACK": (lambda request: True)}
    INTERNAL_IPS = ["0.0.0.0"]

    DEBUG_APPS = os.getenv("DEBUG_APPS")
    if DEBUG_APPS:
        INSTALLED_APPS.append(*DEBUG_APPS.split(","))

    DEBUG_MIDDLEWARE = os.getenv("DEBUG_MIDDLEWARE")
    if DEBUG_MIDDLEWARE:
        MIDDLEWARE.append(*DEBUG_MIDDLEWARE.split(","))
```

Now you can see the debug panel in your admin url (localhost:8000/admin) and you can choose the route you want to see the requests to the bank in a given view with timing details and explain options and see the most problematic query of your stream.