#
# Copyright (C) 2026 NDS Billing Project
#

include $(TOPDIR)/rules.mk

PKG_NAME:=nds-profile
PKG_VERSION:=1.0.0
PKG_RELEASE:=2

PKG_MAINTAINER:=NDS Billing Project
PKG_LICENSE:=GPL-2.0-or-later

include $(INCLUDE_DIR)/package.mk

define Package/nds-profile
  SECTION:=net
  CATEGORY:=Network
  TITLE:=NDS Billing Default Profile
  # nds-hooks is named explicitly because the profile points openNDS's binauth
  # option straight at the script it installs.
  DEPENDS:=+opennds +nds-agent +nds-hooks +dnsmasq-full +firewall4 +kmod-nft-core
endef

define Package/nds-profile/description
  Default UCI configuration for guest WiFi, openNDS FAS level 4,
  walled garden, and IPv6 disable on guest interface.
endef

# UCI defaults only; skip the default configure/compile recipes, which would
# otherwise run make in an empty build directory and fail.
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Configure
endef

define Build/Compile
endef

define Package/nds-profile/install
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/99-nds-profile $(1)/etc/uci-defaults/
	$(INSTALL_DIR) $(1)/etc/init.d
	$(INSTALL_BIN) ./files/etc/init.d/nds-late $(1)/etc/init.d/
endef

$(eval $(call BuildPackage,nds-profile))
