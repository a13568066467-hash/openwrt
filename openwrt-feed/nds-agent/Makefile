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
  DEPENDS:=+ucode +ucode-mod-fs +ucode-mod-uloop +ucode-mod-uci +ucode-mod-digest +ucode-mod-uclient +ucode-mod-json-c +opennds +nds-hooks
endef

define Package/nds-agent/description
  ucode daemon for combined quota enforcement, usage reporting,
  and cloud sync for NDS billing system.
endef

define Package/nds-agent/install
	$(INSTALL_DIR) $(1)/usr/lib/nds-agent
	$(INSTALL_BIN) ./files/usr/lib/nds-agent/main.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_BIN) ./files/usr/lib/nds-agent/ndsctl.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_BIN) ./files/usr/lib/nds-agent/quota.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_BIN) ./files/usr/lib/nds-agent/sync.uc $(1)/usr/lib/nds-agent/
	$(INSTALL_DIR) $(1)/etc/config
	$(INSTALL_CONF) ./files/etc/config/nds-agent $(1)/etc/config/
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/nds-agent $(1)/etc/init.d/
endef

$(eval $(call BuildPackage,nds-agent))
