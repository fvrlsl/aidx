const { request } = require("../../utils/request");

Page({
  data: { cases: [], ranks: [] },
  onShow() {
    request("/cases?page_size=4", "GET").then((r) => this.setData({ cases: r.items }));
    request("/rankings?type=benchmark&limit=5", "GET").then((r) => this.setData({ ranks: r.items }));
  },
  goSearch() {
    wx.navigateTo({ url: "/pages/search/search" });
  },
  goCase(e) {
    wx.navigateTo({ url: `/pages/case/case?id=${e.currentTarget.dataset.id}` });
  },
  goMerchant(e) {
    wx.navigateTo({ url: `/pages/merchant/merchant?id=${e.currentTarget.dataset.id}` });
  },
});
