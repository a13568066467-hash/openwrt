#
# Copyright (C) 2026 NDS Billing Project
#

include $(TOPDIR)/rules.mk

PKG_NAME:=nds-hooks
PKG_VERSION:=1.0.0
PKG_RELEASE:=1

PKG_MAINTAINER:=NDS Billing Project
PKG_LICENSE:=GPL-2.0-or-later

include $(INCLUDE_DIR)/package.mk

define Package/nds-hooks
  SECTION:=net
  CATEGORY:=Network
  TITLE:=NDS Billing BinAuth Hooks
  DEPENDS:=+opennds
endef

define Package/nds-hooks/description
  Custom BinAuth hooks for session event capture and quota echo.
endef

define Package/nds-hooks/install
	$(INSTALL_DIR) $(1)/usr/lib/opennds
	$(INSTALL_BIN) ./files/usr/lib/opennds/custombinauth.sh $(1)/usr/lib/opennds/
endef

$(eval $(call BuildPackage,nds-hooks))
