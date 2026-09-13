const { request } = require("../../utils/request");
Page({
  data: { me: {} },
  onShow() {
    request("/me", "GET").then((me) => this.setData({ me })).catch(() => {});
  },
  rules() { wx.navigateTo({ url: "/pages/rules/rules" }); },
  tip() { wx.navigateTo({ url: "/pages/tip/tip" }); },
});
