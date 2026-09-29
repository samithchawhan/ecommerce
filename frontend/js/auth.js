const Auth = {
  user: null,

  load() {
    const user = localStorage.getItem('volta_user');
    if (user) try { this.user = JSON.parse(user); } catch {}
    this.renderNav();
  },

  setUser(user, token) {
    this.user = user;
    localStorage.setItem('volta_user', JSON.stringify(user));
    localStorage.setItem('volta_token', token);
    this.renderNav();
  },

  logout() {
    this.user = null;
    localStorage.removeItem('volta_user');
    localStorage.removeItem('volta_token');
    this.renderNav();
    window.location.href = '/index.html';
  },

  renderNav() {
    const menu = document.getElementById('authMenu');
    if (!menu) return;
    if (this.user) {
      menu.innerHTML = `
        <span class="user-greeting">Hi, <strong>${this.user.name.split(' ')[0]}</strong></span>
        <button class="btn-auth" onclick="window.location.href='../pages/orders.html'">Orders</button>
        <button class="btn-auth" onclick="Auth.logout()">Sign out</button>
      `;
    } else {
      menu.innerHTML = `
        <button class="btn-auth" onclick="window.location.href='pages/login.html'">Sign in</button>
        <button class="btn-auth primary" onclick="window.location.href='pages/register.html'">Register</button>
      `;
    }
  },

  requireAuth(redirect = '../pages/login.html') {
    if (!this.user) {
      window.location.href = redirect;
      return false;
    }
    return true;
  }
};

Auth.load();
