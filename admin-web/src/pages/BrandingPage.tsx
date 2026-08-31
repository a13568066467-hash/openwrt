import { useEffect, useState } from 'react';
import { Form, Input, Button, Upload, message, Row, Col, Card } from 'antd';
import type { UploadProps } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useQueryClient } from '@tanstack/react-query';
import { adminApi, BrandingConfig } from '../api';
import { useBranding } from '../hooks/useBranding';
import PageShell from '../components/PageShell';

const MAX_SIZE = 1024 * 1024;

function readFileAsDataURL(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function LogoUpload({
  label,
  value,
  onChange,
}: {
  label: string;
  value?: string;
  onChange?: (v: string) => void;
}) {
  const uploadProps: UploadProps = {
    accept: 'image/png,image/jpeg,image/gif,image/svg+xml',
    showUploadList: false,
    beforeUpload: async (file) => {
      if (file.size > MAX_SIZE) {
        message.error('图片不能超过 1MB');
        return Upload.LIST_IGNORE;
      }
      const dataUrl = await readFileAsDataURL(file);
      onChange?.(dataUrl);
      return false;
    },
  };

  return (
    <div className="branding-upload">
      <div className="branding-upload__label">{label}</div>
      <Upload {...uploadProps}>
        <div className="branding-upload__box">
          {value ? (
            <img src={value} alt={label} className="branding-upload__preview" />
          ) : (
            <div className="branding-upload__placeholder">
              <PlusOutlined />
              <span>上传图片</span>
            </div>
          )}
        </div>
      </Upload>
      {value && (
        <Button type="link" size="small" danger onClick={() => onChange?.('')}>
          移除
        </Button>
      )}
      <div className="branding-upload__hint">支持 PNG / JPG / GIF / SVG，建议 200×200，最大 1MB</div>
    </div>
  );
}

export default function BrandingPage() {
  const qc = useQueryClient();
  const { data } = useBranding();
  const [form] = Form.useForm<BrandingConfig>();
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (data) form.setFieldsValue(data);
  }, [data, form]);

  const handleSave = async () => {
    const values = await form.validateFields();
    setSaving(true);
    try {
      await adminApi.updateBranding(values);
      message.success('Logo 设置已保存');
      qc.invalidateQueries({ queryKey: ['branding'] });
    } catch {
      message.error('保存失败，请检查图片大小与格式');
    } finally {
      setSaving(false);
    }
  };

  return (
    <PageShell
      title="Logo 设置"
      extra={
        <Button type="primary" loading={saving} onClick={handleSave}>
          保存设置
        </Button>
      }
    >
      <Form form={form} layout="vertical">
        <Row gutter={24}>
          <Col xs={24} md={12}>
            <Card size="small" title="文字标识" bordered={false} className="branding-card">
              <Form.Item name="site_title" label="侧边栏标题">
                <Input placeholder="NDS 管理" maxLength={32} />
              </Form.Item>
              <Form.Item name="login_title" label="登录页标题">
                <Input placeholder="NDS 管理面板" maxLength={32} />
              </Form.Item>
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card size="small" title="预览" bordered={false} className="branding-card">
              <div className="branding-preview">
                <div className="branding-preview__sider">
                  <Form.Item noStyle shouldUpdate>
                    {() => {
                      const adminLogo = form.getFieldValue('admin_logo');
                      const siteTitle = form.getFieldValue('site_title') || 'NDS 管理';
                      return adminLogo ? (
                        <img src={adminLogo} alt="" className="branding-preview__logo" />
                      ) : (
                        <span className="branding-preview__text">{siteTitle}</span>
                      );
                    }}
                  </Form.Item>
                </div>
                <div className="branding-preview__login">
                  <Form.Item noStyle shouldUpdate>
                    {() => {
                      const adminLogo = form.getFieldValue('admin_logo');
                      const loginTitle = form.getFieldValue('login_title') || 'NDS 管理面板';
                      return (
                        <>
                          {adminLogo && <img src={adminLogo} alt="" className="branding-preview__logo-lg" />}
                          <div>{loginTitle}</div>
                        </>
                      );
                    }}
                  </Form.Item>
                </div>
              </div>
            </Card>
          </Col>
        </Row>

        <Row gutter={24} style={{ marginTop: 8 }}>
          <Col xs={24} md={12}>
            <Form.Item name="admin_logo">
              <LogoUpload label="管理端 Logo（侧边栏 / 登录页）" />
            </Form.Item>
          </Col>
          <Col xs={24} md={12}>
            <Form.Item name="user_logo">
              <LogoUpload label="用户端 H5 Logo" />
            </Form.Item>
          </Col>
        </Row>
      </Form>
    </PageShell>
  );
}
