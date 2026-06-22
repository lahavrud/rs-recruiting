"""Single source of truth for legal-document version strings.

Both the privacy policy and the site terms of service are versioned
independently. Backend persists whichever version was current at the
moment of acceptance so we can later prove which text the user agreed to.

Bump these whenever the corresponding text in
`frontend/src/locales/he.json` changes in a way that affects what the
user agreed to. Keep them in sync with the version line at the top of
each document.
"""

CURRENT_PRIVACY_POLICY_VERSION = "1.2"
CURRENT_TERMS_OF_SERVICE_VERSION = "1.1"
