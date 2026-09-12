const { request } = require("../../utils/request");
Page({
  data: { items: [] },
  onShow() {
    request("/cases?page_size=20", "GET").then((r) => this.setData({ items: r.items }));
  },
  go(e) {
    wx.navigateTo({ url: `/pages/case/case?id=${e.currentTarget.dataset.id}` });
  },
});
