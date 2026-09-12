const BASE = "http://127.0.0.1:8000/api/v1";

function request(path, method, data) {
  const app = getApp();
  return new Promise((resolve, reject) => {
    wx.request({
      url: BASE + path,
      method,
      data,
      header: {
        "content-type": "application/json",
        Authorization: app.globalData.token ? `Bearer ${app.globalData.token}` : "",
      },
      success: (res) => {
        if (res.statusCode >= 200 && res.statusCode < 300) resolve(res.data);
        else reject(new Error((res.data && res.data.detail) || `HTTP ${res.statusCode}`));
      },
      fail: (e) => reject(e),
    });
  });
}

function login() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: (r) => {
        request("/auth/login", "POST", { code: r.code || `mp_${Date.now()}`, nickname: "小程序用户" })
          .then((d) => {
            getApp().globalData.token = d.token;
            resolve(d);
          })
          .catch(reject);
      },
      fail: () => {
        request("/auth/login", "POST", { code: `mp_${Date.now()}`, nickname: "小程序用户" })
          .then((d) => {
            getApp().globalData.token = d.token;
            resolve(d);
          })
          .catch(reject);
      },
    });
  });
}

module.exports = { request, login };
