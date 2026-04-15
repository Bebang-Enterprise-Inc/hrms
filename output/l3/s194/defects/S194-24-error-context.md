# Page snapshot

```yaml
- generic [active] [ref=e1]:
  - generic [ref=e3]:
    - generic [ref=e4]:
      - generic [ref=e6]: BT
      - heading "BEI Tasks" [level=1] [ref=e7]
      - paragraph [ref=e8]: Modern Task Management for Bebang Enterprise
    - generic [ref=e9]:
      - generic [ref=e10]:
        - heading "Sign in to your account" [level=2] [ref=e11]
        - paragraph [ref=e12]: Choose your preferred sign-in method
      - generic [ref=e13]:
        - button "Sign in with Google" [ref=e14]
        - generic [ref=e18]: or continue with email
        - generic [ref=e19]:
          - generic [ref=e20]:
            - generic [ref=e21]: Username or Email
            - textbox "Username or Email" [ref=e22]:
              - /placeholder: Administrator or you@company.com
              - text: test.warehouse@bebang.ph
          - generic [ref=e23]:
            - generic [ref=e24]: Password
            - generic [ref=e25]:
              - textbox "••••••••" [ref=e26]: BeiTest2026!
              - button "Show password" [ref=e27]:
                - img
                - generic [ref=e28]: Show password
          - link "Forgot password?" [ref=e30] [cursor=pointer]:
            - /url: https://hq.bebang.ph/login#forgot
          - button "Sign in" [ref=e31]
        - paragraph [ref=e32]: By signing in, you agree to the company's terms of service
  - region "Notifications alt+T"
  - alert [ref=e33]
```