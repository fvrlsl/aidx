const { login } = require("./utils/request");

App({
  globalData: { token: "" },
  onLaunch() {
    login().catch((e) => console.warn("login failed", e));
  },
});
