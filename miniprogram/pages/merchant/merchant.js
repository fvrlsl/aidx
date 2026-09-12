const { request } = require("../../utils/request");

Page({
  data: { m: {}, ev: [], sum: {}, form: { level: 4, identity_claim: "customer", comment: "" } },
  onLoad(q) {
    this.id = q.id;
    this.reload();
  },
  reload() {
    request(`/merchants/${this.id}`, "GET").then((m) => this.setData({ m }));
    request(`/merchants/${this.id}/evidence?page_size=30`, "GET").then((r) => this.setData({ ev: r.items }));
    request(`/merchants/${this.id}/ratings/summary`, "GET").then((sum) => this.setData({ sum }));
  },
  setLevel(e) {
    this.setData({ "form.level": Number(e.currentTarget.dataset.v) });
  },
  setClaim(e) {
    this.setData({ "form.identity_claim": e.currentTarget.dataset.v });
  },
  setComment(e) {
    this.setData({ "form.comment": e.detail.value });
  },
  submit() {
    request(`/ratings/${this.id}`, "PUT", this.data.form).then((r) => {
      wx.showToast({ title: r.message || "已提交", icon: "none" });
      this.reload();
    }).catch((e) => wx.showToast({ title: e.message, icon: "none" }));
  },
  tip() {
    wx.navigateTo({ url: `/pages/tip/tip?id=${this.id}` });
  },
  feedback() {
    wx.navigateTo({ url: `/pages/feedback/feedback?id=${this.id}` });
  },
  rules() {
    wx.navigateTo({ url: "/pages/rules/rules" });
  },
});
