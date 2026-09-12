const { request } = require("../../utils/request");
Page({
  data: { type: "benchmark", items: [] },
  onShow() { this.load(); },
  load() {
    request(`/rankings?type=${this.data.type}`, "GET").then((r) => this.setData({ items: r.items }));
  },
  setType(e) {
    this.setData({ type: e.currentTarget.dataset.v }, () => this.load());
  },
  go(e) {
    wx.navigateTo({ url: `/pages/merchant/merchant?id=${e.currentTarget.dataset.id}` });
  },
});
