const { request } = require("../../utils/request");
Page({
  data: { c: {} },
  onLoad(q) {
    request(`/cases/${q.id}`, "GET").then((c) => this.setData({ c }));
  },
  go(e) {
    wx.navigateTo({ url: `/pages/merchant/merchant?id=${e.currentTarget.dataset.id}` });
  },
});
