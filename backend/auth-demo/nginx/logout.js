// RP-initiated logout helper for the BFF front door.
//
// Invoked as a content handler AFTER `auth_request`, so the id_token that
// oauth2-proxy returned (in the Authorization header, captured into
// $logout_bearer via auth_request_set) is available here. We pass it as
// `id_token_hint` so Keycloak logs out silently (no confirmation page), and set
// `post_logout_redirect_uri` back through /oauth2/sign_out to also clear the
// oauth2-proxy session cookie. The token is used server-side only — it never
// reaches the browser JS.

var KEYCLOAK_LOGOUT =
  'http://localhost:8081/realms/oqtopus/protocol/openid-connect/logout';
// After the IdP logout, bounce through the proxy sign_out (clears its cookie),
// then land on the app root.
var POST_LOGOUT = 'http://localhost:4200/oauth2/sign_out?rd=/';

function redirect(r) {
  var bearer = r.variables.logout_bearer || '';
  var idToken = bearer.replace(/^Bearer\s+/i, '');
  var url =
    KEYCLOAK_LOGOUT +
    '?id_token_hint=' + idToken +
    '&post_logout_redirect_uri=' + encodeURIComponent(POST_LOGOUT);
  r.return(302, url);
}

export default { redirect };
