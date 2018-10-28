# DCadgrinder
Bot to watch ads for DC

## Proxy with authentication
Neither [chromedriver][cd] nor [geckodriver][gd] allow authentication on proxy servers(at least not without considerable overhead). So if the proxy to be used needs basic username-password authentication, it is recommended to channel the traffic through a local proxy, which authenticates itself to the desired remote proxy. Example:
```json
{
    "url": "localhost",
    "port": 3128
}
```
Now the traffic can be forwarded to the authentication requiring proxy via your local proxy server of trust - for example [squid](http://www.squid-cache.org/) with the following settings added to its config file:
```glsl
# Use peer username:password@myproxy.com:8080
cache_peer myproxy.com parent 8080 0 \
  no-query \
  default \
  login=username:password \
  name=myproxy
cache_peer_access myproxy allow all
# Disable DIRECT connection to enforce remote proxy
never_direct allow all
```

[gd]: https://github.com/mozilla/geckodriver
[cd]: https://sites.google.com/a/chromium.org/chromedriver/