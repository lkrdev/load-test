Project: /looker/docs/_project.yaml
Book: /looker/book-files/looker-guides/_book.yaml
description: Learn about cookieless embedding.

{% include "looker/_local_variables.html" %}

{# disableFinding("admin") #}

# Cookieless embedding

When {{looker_name}} is embedded in an iframe using [signed embedding](/looker/docs/single-sign-on-embedding), some browsers default to a cookie policy that blocks third-party cookies. Third-party cookies are rejected when the embedded iframe is loaded from a domain that is different from the domain that loads the embedding application. You can generally work around this limitation by requesting and using a vanity domain. However, vanity domains can't be used in some scenarios. It is for these scenarios that {{looker_name}} cookieless embedding can be used.

Note: You can view a list of the cookies that {{looker_name}} uses on the [{{looker_name}} cookie list](/looker/docs/cookie-list) documentation page.

## How does cookieless embedding work?

When third-party cookies are not blocked, a session cookie is created when a user initially logs in to {{looker_name}}. This cookie is sent with every user request, and the {{looker_name}} server uses it to establish the identity of the user who initiated the request. When cookies are blocked, the cookie is not sent with a request, so the {{looker_name}} server can't identify the user who is associated with the request.

To solve this problem, {{looker_name}} cookieless embed associates tokens with each request that can be used to recreate the user session in the {{looker_name}} server. It is the responsibility of the embedding application to get these tokens and make them available to the {{looker_name}} instance that is running in the embedded iframe. The process of obtaining and providing these tokens is described in the rest of this document.

Important: {{looker_name}} has two embed APIs: the {{looker_name}} Embed SDK and a JavaScript `window.postMessage`-based API. {{looker_name}} cookieless embed works for both of these APIs. The {{looker_name}} Embed SDK simplifies how the embedding client interacts with the {{looker_name}} iframe, but examples that illustrate the use of the `window.postMessage` API are provided in this document. The {{looker_name}} cookieless embed API is different from the {{looker_name}} signed embed URL signing API and requires different processing in the embedding application server. The {{looker_name}} signed embed URL signing API and the {{looker_name}} cookieless embed API may be used at the same time, although each individual user _must_ use only one method or the other.

To use either API, the embedding application must be able to authenticate into the {{looker_name}} API with admin privileges. The embed domain must also either be listed in the [**Embed Domain Allowlist**](/looker/docs/admin-panel-platform-embed#embedded_domain_allowlist), or, if using {{looker_name}} 23.8 or later, the embed domain can be included when the [cookieless session is acquired](#acquire_session).

### Creating a {{looker_name}} embed iframe {:#creating-a-looker-embed-iframe}

The following sequence diagram illustrates the creation of an embed iframe. Multiple iframes may be generated either simultaneously or at some point in the future. When implemented correctly, the iframe will automatically join the session that is created by the first iframe. The {{looker_name}} Embed SDK simplifies this process by automatically joining the existing session.

<img src="/looker/docs/images/create-embed-iframe-workflow-2440.png" alt="A sequence diagram that illustrates the creation of an embed iframe." />

1. The user performs an action in the embedding application that results in the creation of a {{looker_name}} iframe.
2. The embedding application client acquires a {{looker_name}} session. The {{looker_name}} Embed SDK can be used to initiate this session, but an endpoint URL or a callback function must be provided. If a callback function is used, it will call the embedding application server to acquire the {{looker_name}} embed session. Otherwise, the Embed SDK will call the provided endpoint URL.
3. The embedding application server uses the {{looker_name}} API to acquire an embed session. This API call is similar to the {{looker_name}} signed embed signing process, as it accepts the embed user definition as input. If a {{looker_name}} embed session already exists for the calling user, the associated session reference token should be included in the call. This will be explained in greater detail in the [Acquire session](#acquire_session) section of this document.
4. The acquire embed session endpoint processing is similar to the signed `/login/embed/(signed url)` endpoint, in that it expects the {{looker_name}} embed user definition as the body of the request, rather than in the URL. The acquire embed session endpoint process validates, and then creates or updates, the embed user. It also can accept an existing session reference token. This is important as it allows multiple {{looker_name}} embedded iframes to share the same session. The embed user won't be updated if a session reference token is provided and the session has not expired. This supports the use case where one iframe is created using a signed embed URL and other iframes are created without a signed embed URL. In this case, the iframes without signed embed URLs will inherit the cookie from the first session.
5. The {{looker_name}} API call returns four tokens, each with a time to live (TTL):
  + Authorization token (TTL = 30 seconds)
  + Navigation token (TTL = 10 minutes)
  + API token (TTL = 10 minutes)
  + Session reference token (TTL = remaining lifetime of the session)
6. The embedding application server must keep track of the data that is returned by the {{looker_name}} data and associate it with both the calling user and the user agent of the calling user's browser. Suggestions for how to do this are provided in the [Generate tokens](#generate_tokens) section of this document. This call will return the authorization token, a navigation token, and an API token, along with *all* the associated TTLs. The session reference token should be secured and not exposed in the calling browser.
7. Once the tokens have been returned to the browser, a {{looker_name}} embed login URL must be constructed. The {{looker_name}} Embed SDK will construct the embed login URL automatically. To use the `windows.postMessage` API to construct the embed login URL, see the [Using the {{looker_name}} `windows.postMessage` API](#using-the-looker-windowspostmessage-api) section of this document for examples.

  The login URL does not contain the signed embed user detail. It contains the target URI, including the navigation token, and the authorization token as a query parameter. The authorization token must be used within 30 seconds and can be used only once. If additional iframes are required, an embed session must be acquired again. However, if the session reference token is provided, the authorization token will be associated with the same session.
9. The {{looker_name}} embed login endpoint determines if the login is for cookieless embed, which is denoted by the presence of the authorization token. If the authorization token is valid, it checks the following:
  + The associated session is still valid.
  + The associated embed user is still valid.
  + The browser user agent that is associated with the request matches the browser agent that is associated with the session.
10. If the checks from the previous step pass, the request is redirected using the target URI that is contained in the URL. This is the same process as for the {{looker_name}} signed embed login.
11. This request is the redirect to launch the {{looker_name}} dashboard. This request will have the navigation token as a parameter.
12. Before the endpoint is executed, the {{looker_name}} server looks for the navigation token in the request. If the server finds the token, it checks for the following:
  + The associated session is still valid.
  + The browser user agent that is associated with the request matches the browser agent that is associated with the session.

  If valid, the session is restored for the request and the dashboard request runs.
13. The HTML to load the dashboard is returned to the iframe.
14. The {{looker_name}} UI that is running in the iframe determines that the dashboard HTML is a cookieless embed response. At that point, the {{looker_name}} UI sends a message to the embedding application to request the tokens that were retrieved in step 6. The UI then waits until it receives the tokens. If the tokens don't arrive, a message is displayed.
15. The embedding application sends the tokens to the {{looker_name}} embedded iframe.
16. When the tokens are received, the {{looker_name}} UI that is running in the iframe starts the process to render the request object. During this process, the UI will make API calls to the {{looker_name}} server. The API token that was received in step 15 is automatically injected as a header into all API requests.
17. Before any endpoint is executed, the {{looker_name}} server looks for the API token in the request. If the server finds the token, the server checks for the following:
  + The associated session is still valid.
  + The browser user agent that is associated with the request matches the browser agent that is associated with the session.

  If the session is valid, it is restored for the request, and the API request runs.
18. Dashboard data is returned.
19. The dashboard is rendered.
20. The user has control over the dashboard.

### Generating new tokens

The following sequence diagram illustrates the generation of new tokens.

<img src="/looker/docs/images/generating-new-tokens-2220.png" alt="A sequence diagram that illustrates generating new tokens." />

1. The {{looker_name}} UI that is running in the embedded iframe monitors the TTL of the embed tokens.
2. When the tokens approach expiration, the {{looker_name}} UI sends a refresh token message to the embedding application client.
3. The embedding application client then requests new tokens from an endpoint that is implemented in the embedding application server. The [{{looker_name}} Embed SDK](https://github.com/looker-open-source/embed-sdk) will request new tokens automatically, but the endpoint URL or a callback function must be provided. If the callback function is used, it will call the embedding application server to generate new tokens. Otherwise, the Embed SDK will call the provided endpoint URL.
4. The embedding application finds the `session_reference_token` that is associated with the embed session. The example that is provided in the [{{looker_name}} Embed SDK Git repository](https://github.com/looker-open-source/embed-sdk) uses session cookies, but a distributed server-side cache, Redis for example, can also be used.
5. The embedding application server calls the {{looker_name}} server with a request to generate tokens. This request also requires recent API and navigation tokens in addition to the user agent of the browser that initiated the request.
6. The {{looker_name}} server validates the user agent, the session reference token, the navigation token, and the API token. If the request is valid, new tokens are generated.
7. The tokens are returned to the calling embedding application server.
8. The embedding application server strips the session reference token from the response and returns the remaining response to the embedding application client.
9. The embedding application client sends the newly generated tokens to the {{looker_name}} UI. The {{looker_name}} Embed SDK will do this automatically. Embedding application clients that use the `windows.postMessage` API will be responsible for sending the tokens. Once the {{looker_name}} UI receives the tokens, they will be used in subsequent API calls and page navigations.

## Implementing {{looker_name}} cookieless embed {:#implementing-looker-cookieless-embed}

{{looker_name}} cookieless embed can be implemented by using either the {{looker_name}} Embed SDK or the `windows.postMessage` API. You can use the [{{looker_name}} Embed SDK](https://github.com/looker-open-source/embed-sdk) method, but an example showing how to use the `windows.postMessage` API is also available. Detailed explanations of both implementations can be found in the {{looker_name}} [Embed SDK README file](https://github.com/looker-open-source/embed-sdk#readme). The [Embed SDK git repository](https://github.com/looker-open-source/embed-sdk) also contains working implementations.

### Configuring the {{looker_name}} instance {:#configuring-the-looker-instance}

Cookieless embedding has commonality with {{looker_name}} [signed embedding](/looker/docs/single-sign-on-embedding). To use cookieless embedding, an admin must enable [**Embed SSO Authentication**](/looker/docs/admin-panel-platform-embed#embed_sso_authentication). However, unlike {{looker_name}} signed embedding, cookieless embedding does not use the **Embed Secret** setting. Cookieless embedding uses a JSON Web Token (JWT) in the form of an **Embed JWT Secret** setting, which can be set or reset on the [**Embed** page](/looker/docs/admin-panel-platform-embed) in the **Platform** section of the **Admin** menu.

Setting the JWT secret is *not* required, since the very first attempt to create a cookieless embed session will create the JWT. Avoid resetting this token, as doing so will invalidate all active cookieless embed sessions.

Unlike the embed secret, the embed JWT secret is never exposed, as it is only used internally in the {{looker_name}} server.

### Application client implementation

This section includes examples of how to implement cookieless embedding in the application client and contains the following subsections:

- [Installing and updating the {{looker_name}} Embed SDK](#installing-or-updating-the-looker-embed-sdk)
- [Using the {{looker_name}} Embed SDK](#using-the-looker-embed-sdk)
- [Using the {{looker_name}} `windows.postMessage` API](#using-the-looker-windowspostmessage-api)

#### Installing or updating the {{looker_name}} Embed SDK {:#installing-or-updating-the-looker-embed-sdk}

The following {{looker_name}} SDK versions are required to use cookieless embedding:

{% verbatim %}

```javascript
@looker/embed-sdk >= 2.0.0
@looker/sdk >= 22.16.0
```

{% endverbatim %}

#### Using the {{looker_name}} Embed SDK {:#using-the-looker-embed-sdk}

A new initialization method has been added to the Embed SDK to initiate the cookieless session. This method accepts either two URL strings or two callback functions. The URL strings should reference endpoints in the embedding application server. Implementation details of these endpoints on the application server are covered in the [Application server implementation](#application_server_implementation) section of this document.

{% verbatim %}

```javascript
getEmbedSDK().initCookieless(
  runtimeConfig.lookerHost,
  '/acquire-embed-session',
  '/generate-embed-tokens'
)
```

{% endverbatim %}

The following example shows how callbacks are used. Callbacks should only be used when it is necessary for the embedding client application to know the status of the {{looker_name}} embedding session. You can also use the [`session:status` event](/looker/docs/embedded-javascript-events#session:status), making it unnecessary to use callbacks with the Embed SDK.

Note: The following is sample code, some variation of which needs to be implemented. This implementation stores the `api_token` and `nav_token` in the client and uses a `PUT` method to send data to the server. An alternate implementation is to store the `api_token` and `nav_token` in session data, which allows the client to use a `GET` method. The example code in the [Embed SDK GitHub repository](https://github.com/looker-open-source/embed-sdk) uses the latter mechanism.

{% verbatim %}

```javascript
const acquireEmbedSessionCallback =
  async (): Promise<LookerEmbedCookielessSessionData> => {
    const resp = await fetch('/acquire-embed-session')
    if (!resp.ok) {
      console.error('acquire-embed-session failed', { resp })
      throw new Error(
        `acquire-embed-session failed: ${resp.status} ${resp.statusText}`
      )
    }
    return (await resp.json()) as LookerEmbedCookielessSessionData
  }

const generateEmbedTokensCallback =
  async ({ api_token, navigation_token }): Promise<LookerEmbedCookielessSessionData> => {
    const resp = await fetch('/generate-embed-tokens', {
      method: 'PUT',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ api_token, navigation_token }),
    })
    if (!resp.ok) {
      console.error('generate-embed-tokens failed', { resp })
      throw new Error(
        `generate-embed-tokens failed: ${resp.status} ${resp.statusText}`
      )
    }
    return (await resp.json()) as LookerEmbedCookielessSessionData
  }

getEmbedSDK().initCookieless(
  runtimeConfig.lookerHost,
  acquireEmbedSessionCallback,
  generateEmbedTokensCallback
)
```

{% endverbatim %}

#### Using the {{looker_name}} `windows.postMessage` API {:#using-the-looker-windowspostmessage-api}

You can view a detailed example of using the `windows.postMessage` API in the [`message_example.ts`](https://github.com/looker-open-source/embed-sdk/blob/master/demo/message_example.ts) and [`message_utils.ts`](https://github.com/looker-open-source/embed-sdk/blob/master/demo/message_utils.ts) files in the Embed SDK Git repository. Highlights of the example are detailed here.

The following example demonstrates how to build the URL for the iframe. The callback function is identical to the `acquireEmbedSessionCallback` example seen previously.

{% verbatim %}

```javascript
  private async getCookielessLoginUrl(): Promise<string> {
    const { authentication_token, navigation_token } =
      await this.embedEnvironment.acquireSession()
    const url = this.embedUrl.startsWith('/embed')
      ? this.embedUrl
      : `/embed${this.embedUrl}`
    const embedUrl = new URL(url, this.frameOrigin)
    if (!embedUrl.searchParams.has('embed_domain')) {
      embedUrl.searchParams.set('embed_domain', window.location.origin)
    }
    embedUrl.searchParams.set('embed_navigation_token', navigation_token)
    const targetUri = encodeURIComponent(
      `${embedUrl.pathname}${embedUrl.search}${embedUrl.hash}`
    )
    return `${embedUrl.origin}/login/embed/${targetUri}?embed_authentication_token=${authentication_token}`
  }
```

{% endverbatim %}

The following example demonstrates how to listen for token requests, generate new tokens, and send them to {{looker_name}}. The callback function is identical to the previous `generateEmbedTokensCallback` example.

{% verbatim %}

```javascript
      this.on(
        'session:tokens:request',
        this.sessionTokensRequestHandler.bind(this)
      )

  private connected = false

  private async sessionTokensRequestHandler(_data: any) {
    const contentWindow = this.getContentWindow()
    if (contentWindow) {
      if (!this.connected) {
        // When not connected the newly acquired tokens can be used.
        const sessionTokens = this.embedEnvironment.applicationTokens
        if (sessionTokens) {
          this.connected = true
          this.send('session:tokens', this.embedEnvironment.applicationTokens)
        }
      } else {
        // If connected, the embedded Looker application has decided that
        // it needs new tokens. Generate new tokens.
        const sessionTokens = await this.embedEnvironment.generateTokens()
        this.send('session:tokens', sessionTokens)
      }
    }
  }

  send(messageType: string, data: any = {}) {
    const contentWindow = this.getContentWindow()
    if (contentWindow) {
      const message: any = {
        type: messageType,
        ...data,
      }
      contentWindow.postMessage(JSON.stringify(message), this.frameOrigin)
    }
    return this
  }
```

{% endverbatim %}

### Application server implementation

This section includes examples of how to implement cookieless embedding in the application server and contains the following subsections:

- [Basic implementation](#basic_implementation)
- [Acquire session](#acquire_session)
- [Generate tokens](#generate_tokens)
- [Implementation considerations](#implementation_considerations)

#### Basic implementation

The embedding application is required to implement two server-side endpoints that will invoke {{looker_name}} endpoints. This is to ensure that the session reference token remains secure. These are the endpoints:

1. Acquire session &mdash; If a session reference token already exists and is still active, requests for a session will join the existing session. Acquire session is called when an iframe is created.
1. Generate tokens &mdash; {{looker_name}} triggers calls to this endpoint periodically.

#### Acquire session

This example in TypeScript uses the session to save or restore the session reference token. The endpoint does not have to be implemented in TypeScript.

{% verbatim %}

```javascript
  app.get(
    '/acquire-embed-session',
    async function (req: Request, res: Response) {
      try {
        const current_session_reference_token =
          req.session && req.session.session_reference_token
        const response = await acquireEmbedSession(
          req.headers['user-agent']!,
          user,
          current_session_reference_token
        )
        const {
          authentication_token,
          authentication_token_ttl,
          navigation_token,
          navigation_token_ttl,
          session_reference_token,
          session_reference_token_ttl,
          api_token,
          api_token_ttl,
        } = response
        req.session!.session_reference_token = session_reference_token
        res.json({
          api_token,
          api_token_ttl,
          authentication_token,
          authentication_token_ttl,
          navigation_token,
          navigation_token_ttl,
          session_reference_token_ttl,
        })
      } catch (err: any) {
        res.status(400).send({ message: err.message })
      }
    }
  )

async function acquireEmbedSession(
  userAgent: string,
  user: LookerEmbedUser,
  session_reference_token: string
) {
  await acquireLookerSession()
    try {
    const request = {
      ...user,
      session_reference_token: session_reference_token,
    }
    const sdk = new Looker40SDK(lookerSession)
    const response = await sdk.ok(
      sdk.acquire_embed_cookieless_session(request, {
        headers: {
          'User-Agent': userAgent,
        },
      })
    )
    return response
  } catch (error) {
    console.error('embed session acquire failed', { error })
    throw error
  }
}
```

{% endverbatim %}

Starting in {{looker_name}} 23.8, the embed domain can be included when the cookieless session is acquired. This is an alternative to adding the embed domain using the {{looker_name}} [**Admin > Embed**](/looker/docs/admin-panel-platform-embed) panel. {{looker_name}} saves the embed domain in the {{looker_name}} internal database, so it won't be shown on the **Admin > Embed** panel. Instead, the embed domain is associated with the cookieless session and exists for the duration of the session only. Review the [security best practices](/looker/docs/security-best-practices-embedded-analytics) if you decide to take advantage of this feature.

#### Generate tokens

This example in TypeScript uses the session to save or restore the session reference token. The endpoint does not have to be implemented in TypeScript.

It is important that you know how to handle 400 responses, which occur when tokens are invalid. Although a 400 response being returned shouldn't happen, if it does, it is best practice to terminate the {{looker_name}} embed session. You can terminate the {{looker_name}} embed session by either destroying the embed iframe or by setting the `session_reference_token_ttl` value to zero in the `session:tokens` message. If you set the `session_reference_token_ttl` value to zero, the {{looker_name}} iframe displays a session expired dialog.

A 400 response is not returned when the embed session expires. If the embed session has expired, a 200 response is returned with the `session_reference_token_ttl` value set to zero.

{% verbatim %}

```javascript
  app.put(
    '/generate-embed-tokens',
    async function (req: Request, res: Response) {
      try {
        const session_reference_token = req.session!.session_reference_token
        const { api_token, navigation_token } = req.body as any
        const tokens = await generateEmbedTokens(
          req.headers['user-agent']!,
          session_reference_token,
          api_token,
          navigation_token
        )
        res.json(tokens)
      } catch (err: any) {
        res.status(400).send({ message: err.message })
      }
    }
  )
}
async function generateEmbedTokens(
  userAgent: string,
  session_reference_token: string,
  api_token: string,
  navigation_token: string
) {
  if (!session_reference_token) {
    console.error('embed session generate tokens failed')
    // missing session reference  treat as expired session
    return {
      session_reference_token_ttl: 0,
    }
  }
  await acquireLookerSession()
  try {
    const sdk = new Looker40SDK(lookerSession)
    const response = await sdk.ok(
      sdk.generate_tokens_for_cookieless_session(
        {
          api_token,
          navigation_token,
          session_reference_token: session_reference_token || '',
        },
        {
          headers: {
            'User-Agent': userAgent,
          },
        }
      )
    )
    return {
      api_token: response.api_token,
      api_token_ttl: response.api_token_ttl,
      navigation_token: response.navigation_token,
      navigation_token_ttl: response.navigation_token_ttl,
      session_reference_token_ttl: response.session_reference_token_ttl,
    }
  } catch (error: any) {
    if (error.message?.includes('Invalid input tokens provided')) {
      // The Looker UI does not know how to handle bad
      // tokens. This shouldn't happen but if it does expire the
      // session. If the token is bad there is not much that that
      // the Looker UI can do.
      return {
        session_reference_token_ttl: 0,
      }
    }
    console.error('embed session generate tokens failed', { error })
    throw error
  }
```

{% endverbatim %}

#### Implementation considerations

The embedding application must keep track of the session reference token and must keep it secure. This token should be associated with the embedded application user. The embedding application token can be stored in one of the following ways:

* In the embedded application user's session
* In a server-side cache that is available across a clustered environment
* In a database table that is associated with the user

If the session is stored as a cookie, the cookie should be encrypted. The example in the embed SDK repository uses a session cookie to store the session reference token.

When the {{looker_name}} embed session expires, a dialog will be displayed in the embedded iframe. At this point, the user won't be able to do anything in the embedded instance. When this occurs, the [`session:status` events](/looker/docs/embedded-javascript-events#session:status) will be generated, allowing the embedding application to detect the current state of the embedded {{looker_name}} application and take some kind of action.

An embedding application can detect if the embed session has expired by checking if the `session_reference_token_ttl` value that is returned by the `generate_tokens` endpoint is zero. If the value is zero, then the embed session has expired. Consider using a callback function for generating tokens when the cookieless embed is initializing. The callback function can then determine if the embed session has expired and will destroy the embedded iframe as an alternative to using the default embedded session expired dialog.

### Running the {{looker_name}} cookieless embed example {:#running-the-looker-cookieless-embed-example}

The embed SDK repository contains a node express server and client written in TypeScript that implements an embed application. The examples shown previously are taken from this implementation. The following assumes that your {{looker_name}} instance has been configured to use cookieless embed as described earlier.

You can run the server as follows:

1. Clone the Embed SDK repository &mdash; `git clone git@github.com:looker-open-source/embed-sdk.git`
1. Change the directory &mdash; `cd embed-sdk`
1. Install the dependencies &mdash; `npm install`
1. Configure the server, as shown in the [Configure the server](#configure_the_server) section of this document.
1. Run the server &mdash; `npm run server`

#### Configure the server

Create a `.env` file in the root of the cloned repository (this is included in `.gitignore`).

Important: {{looker_name}} reports are available when the [{{looker_name}} reports feature is enabled](/looker/docs/studio-in-looker). See [Embed {{looker_name}} reports](/looker/docs/embed-reports) for additional requirements and considerations for embedding reports.

The format is as follows:

{% verbatim %}

```javascript
LOOKER_WEB_URL=your-looker-instance-url.com
LOOKER_API_URL=https://your-looker-instance-url.com
LOOKER_DEMO_HOST=localhost
LOOKER_DEMO_PORT=8080
LOOKER_EMBED_SECRET=embed-secret-from-embed-admin-page
LOOKER_CLIENT_ID=client-id-from-user-admin-page
LOOKER_CLIENT_SECRET=client-secret-from-user-admin-page
LOOKER_DASHBOARD_ID=id-of-dashboard
LOOKER_LOOK_ID=id-of-look
LOOKER_EXPLORE_ID=id-of-explore
LOOKER_EXTENSION_ID=id-of-extension
LOOKER_VERIFY_SSL=true
LOOKER_REPORT_ID=id-of-report
LOOKER_QUERY_VISUALIZATION_ID=id-of-query-visualization
```
Tip: `LOOKER_WEB_URL` can also be configured using `LOOKER_EMBED_HOST`. `LOOKER_API_URL` can also be configured using `LOOKER_EMBED_API_URL`.

{% endverbatim %}