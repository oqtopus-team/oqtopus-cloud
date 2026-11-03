// RP-initiated logout helper for the BFF front door.
//
// Invoked as a content handler AFTER `auth_request`, so the id_token that
// oauth2-proxy returned (in the Authorization header, captured into
// $logout_bearer via auth_request_set) is available here. We pass it as
// `id_token_hint` so Keycloak logs out silently (no confirmation page), and set
// `post_logout_redirect_uri` back through /oauth2/sign_out to also clear the
// oauth2-proxy session cookie. The token is used server-side only — it never
// reaches the browser JS.

// Keycloak is published on :8081 of the same host the browser used to reach
// this front door, so derive every URL from the request's Host header instead
// of hard-coding localhost (works for localhost and PUBLIC_HOST alike, and for
// both the user (:4200) and admin (:4201) front doors).
var KEYCLOAK_PORT = '8081';

function redirect(r) {
  var host = r.headersIn.Host || 'localhost';
  var hostname = host.replace(/:\d+$/, '');
  var keycloakLogout =
    'http://' + hostname + ':' + KEYCLOAK_PORT +
    '/realms/oqtopus/protocol/openid-connect/logout';
  // After the IdP logout, bounce through the proxy sign_out (clears its
  // cookie), then land on the app root.
  var postLogout = 'http://' + host + '/oauth2/sign_out?rd=/';

  var bearer = r.variables.logout_bearer || '';
  var idToken = bearer.replace(/^Bearer\s+/i, '');
  var url =
    keycloakLogout +
    '?id_token_hint=' + idToken +
    '&post_logout_redirect_uri=' + encodeURIComponent(postLogout);
  r.return(302, url);
}

export default { redirect };
