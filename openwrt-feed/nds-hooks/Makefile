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
  # jsonfilter parses the parameters the FAS packs into openNDS's custom field.
  DEPENDS:=+opennds +jsonfilter
endef

define Package/nds-hooks/description
  Custom BinAuth hooks for session event capture and quota echo.
endef

# Shell script only; skip the default configure/compile recipes, which would
# otherwise run make in an empty build directory and fail.
define Build/Prepare
	mkdir -p $(PKG_BUILD_DIR)
endef

define Build/Configure
endef

define Build/Compile
endef

# Installed under its own directory rather than /usr/lib/opennds: openNDS
# already ships a custombinauth.sh there, and apk refuses to let one package
# overwrite a file owned by another.
define Package/nds-hooks/install
	$(INSTALL_DIR) $(1)/usr/lib/nds-hooks
	$(INSTALL_BIN) ./files/usr/lib/nds-hooks/binauth.sh $(1)/usr/lib/nds-hooks/
endef

$(eval $(call BuildPackage,nds-hooks))
