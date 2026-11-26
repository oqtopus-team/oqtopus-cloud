// RP-initiated logout helper for the BFF front door.
//
// Invoked as a content handler AFTER `auth_request`, so the id_token that
// oauth2-proxy returned (captured into $logout_bearer) is available. We pass it
// as id_token_hint so Keycloak logs out silently, and set
// post_logout_redirect_uri back through /oauth2/sign_out to clear the proxy
// cookie. The token is used server-side only — it never reaches browser JS.
//
// The Keycloak logout endpoint and post-logout URI are provided by the server
// block via `set $keycloak_logout_url` / `set $post_logout_uri`, so the same
// module serves any deployment hostname.
function redirect(r) {
  var bearer = r.variables.logout_bearer || '';
  var idToken = bearer.replace(/^Bearer\s+/i, '');
  var url =
    r.variables.keycloak_logout_url +
    '?id_token_hint=' + idToken +
    '&post_logout_redirect_uri=' + encodeURIComponent(r.variables.post_logout_uri);
  r.return(302, url);
}

export default { redirect };
