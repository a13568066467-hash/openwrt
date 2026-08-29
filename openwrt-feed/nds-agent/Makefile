#
# Copyright (C) 2026 NDS Billing Project
# Licensed under GPL-2.0
#

include $(TOPDIR)/rules.mk

PKG_NAME:=nds-agent
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_MAINTAINER:=NDS Billing Project
PKG_LICENSE:=GPL-2.0-or-later

include $(INCLUDE_DIR)/package.mk

define Package/nds-agent
  SECTION:=net
  CATEGORY:=Network
  TITLE:=NDS Billing Agent (ucode)
  # The agent polls on a plain sleep loop, so no uloop binding is needed.
  # curl is the HTTPS transport; uclient-fetch is only a fallback.
  DEPENDS:=+ucode +ucode-mod-fs +ucode-mod-uci +curl +opennds +nds-hooks
endef

define Package/nds-agent/description
  ucode daemon for combined quota enforcement, usage reporting,
  and cloud sync for NDS billing system.
endef

# Nothing is compiled: the package only ships ucode and configuration. Without
# these overrides the default recipe would run ./configure and make in an empty
# build directory and fail.
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/nds-agent/install
	$(INSTALL_DIR) $(1)/usr/lib/nds-agent
	$(INSTALL_BIN) ./files/usr/lib/nds-agent/main.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_DATA) ./files/usr/lib/nds-agent/ndsctl.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_DATA) ./files/usr/lib/nds-agent/quota.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_DATA) ./files/usr/lib/nds-agent/http.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_DATA) ./files/usr/lib/nds-agent/cloud.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/nds-agent $(1)/etc/config/
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/nds-agent $(1)/etc/init.d/
endef

$(eval $(call BuildPackage,nds-agent))
