const { request } = require("../../utils/request");
Page({
  data: { md: "" },
  onLoad() {
    request("/rating-rules", "GET").then((r) => this.setData({ md: r.markdown }));
  },
});
