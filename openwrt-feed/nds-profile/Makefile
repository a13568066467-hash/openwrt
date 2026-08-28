#
# Copyright (C) 2026 NDS Billing Project
#

include $(TOPDIR)/rules.mk

PKG_NAME:=nds-profile
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_MAINTAINER:=NDS Billing Project
PKG_LICENSE:=GPL-2.0-or-later

include $(INCLUDE_DIR)/package.mk

define Package/nds-profile
  SECTION:=net
  CATEGORY:=Network
  TITLE:=NDS Billing Default Profile
  DEPENDS:=+opennds +nds-agent +dnsmasq-full +firewall4 +kmod-nft-core
endef

define Package/nds-profile/description
  Default UCI configuration for guest WiFi, openNDS FAS level 4,
  walled garden, and IPv6 disable on guest interface.
endef

define Package/nds-profile/install
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/99-nds-profile $(1)/etc/uci-defaults/
endef

$(eval $(call BuildPackage,nds-profile))
