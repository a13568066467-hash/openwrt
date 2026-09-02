import { useState } from 'react';
import {
  Table, Button, Modal, Form, Input, InputNumber, message, Tag, Drawer, Space, Typography, Divider, Tooltip,
} from 'antd';
import { CopyOutlined, GiftOutlined, KeyOutlined } from '@ant-design/icons';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { adminApi, formatTrafficMB, VoucherBatch, VoucherBatchDetail } from '../api';
import PageShell from '../components/PageShell';

const { Text, Title } = Typography;

const VOUCHER_STATUS: Record<string, { label: string; color: string }> = {
  unused: { label: '未使用', color: 'green' },
  used: { label: '已使用', color: 'default' },
};

export default function VouchersPage() {
  const qc = useQueryClient();
  const [modalOpen, setModalOpen] = useState(false);
  const [codes, setCodes] = useState<string[]>([]);
  const [batchName, setBatchName] = useState('');
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [detail, setDetail] = useState<VoucherBatchDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['voucher-batches'],
    queryFn: () => adminApi.getVoucherBatches().then(r => r.data),
  });

  const openCreate = () => {
    form.resetFields();
    form.setFieldsValue({ valid_days: 90 });
    setCodes([]);
    setBatchName('');
    setModalOpen(true);
  };

  const handleCreate = async () => {
    const values = await form.validateFields();
    const { data: result } = await adminApi.createVoucherBatch(
      values.name,
      values.traffic_mb,
      values.count,
      values.valid_days ?? 90,
    );
    setCodes(result.codes);
    setBatchName(values.name);
    message.success(`已生成 ${result.codes.length} 张卡密`);
    qc.invalidateQueries({ queryKey: ['voucher-batches'] });
  };

  const openDetail = async (batch: VoucherBatch) => {
    setDrawerOpen(true);
    setDetailLoading(true);
    setDetail(null);
    try {
      const { data: d } = await adminApi.getVoucherBatchDetail(batch.id);
      setDetail(d);
    } catch {
      message.error('加载批次详情失败');
      setDrawerOpen(false);
    } finally {
      setDetailLoading(false);
    }
  };

  const copyCodes = (list: string[]) => {
    navigator.clipboard.writeText(list.join('\n'));
    message.success('已复制到剪贴板');
  };

  return (
    <PageShell
      title="卡密管理"
      extra={
        <Button type="primary" icon={<GiftOutlined />} onClick={openCreate}>
          生成卡密批次
        </Button>
      }
    >
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: '批次名称', dataIndex: 'name' },
          {
            title: '面额',
            dataIndex: 'traffic_mb',
            render: (v: number) => formatTrafficMB(v),
          },
          { title: '数量', dataIndex: 'count', width: 80 },
          {
            title: '使用期间',
            dataIndex: 'valid_days',
            width: 100,
            render: (v: number) => (v ? `${v} 天` : '—'),
          },
          {
            title: '创建时间',
            dataIndex: 'created_at',
            render: (v: string) => new Date(v).toLocaleString('zh-CN'),
          },
          {
            title: '操作',
            width: 240,
            render: (_: unknown, r: VoucherBatch) => {
              if (r.count === 1 && r.code) {
                const used = r.code_status === 'used';
                return (
                  <Tooltip title={used ? '已使用' : '点击复制'}>
                    <span
                      className={`voucher-inline-code${used ? ' voucher-inline-code--used' : ''}`}
                      onClick={() => copyCodes([r.code!])}
                      role="button"
                      tabIndex={0}
                    >
                      {r.code}
                      {!used && <CopyOutlined className="voucher-inline-code__icon" />}
                    </span>
                  </Tooltip>
                );
              }
              if (r.count > 2) {
                return (
                  <Button type="link" size="small" onClick={() => openDetail(r)}>
                    详情
                  </Button>
                );
              }
              return null;
            },
          },
        ]}
      />

      <Modal
        className="voucher-modal"
        title={null}
        open={modalOpen}
        onOk={handleCreate}
        onCancel={() => setModalOpen(false)}
        okText="生成卡密"
        cancelText="关闭"
        width={560}
        destroyOnClose
      >
        <div className="voucher-modal__header">
          <div className="voucher-modal__icon">
            <KeyOutlined />
          </div>
          <div>
            <Title level={4} style={{ margin: 0 }}>生成卡密批次</Title>
            <Text type="secondary">批量生成流量充值卡密，生成后请妥善保存</Text>
          </div>
        </div>

        <Divider style={{ margin: '16px 0' }} />

        <Form form={form} layout="vertical" className="voucher-modal__form">
          <Form.Item name="name" label="批次名称" rules={[{ required: true, message: '请输入批次名称' }]}>
            <Input placeholder="例如：暑期促销套餐" />
          </Form.Item>
          <div className="voucher-modal__row">
            <Form.Item
              name="traffic_mb"
              label="面额 (MB)"
              rules={[{ required: true, message: '请输入面额' }]}
              style={{ flex: 1 }}
            >
              <InputNumber style={{ width: '100%' }} min={1} placeholder="1024" />
            </Form.Item>
            <Form.Item
              name="count"
              label="数量"
              rules={[{ required: true, message: '请输入数量' }]}
              style={{ flex: 1 }}
            >
              <InputNumber style={{ width: '100%' }} min={1} max={1000} placeholder="10" />
            </Form.Item>
          </div>
          <Form.Item
            name="valid_days"
            label="使用期间（天）"
            tooltip="用户兑换后，流量有效期的延长天数"
            rules={[{ required: true, message: '请设置使用期间' }]}
          >
            <InputNumber style={{ width: '100%' }} min={1} max={3650} addonAfter="天" />
          </Form.Item>
        </Form>

        {codes.length > 0 && (
          <div className="voucher-modal__result">
            <div className="voucher-modal__result-head">
              <Tag color="success">生成成功 · {batchName}</Tag>
              <Tooltip title="复制全部卡密">
                <Button
                  type="text"
                  size="small"
                  icon={<CopyOutlined />}
                  onClick={() => copyCodes(codes)}
                >
                  复制全部
                </Button>
              </Tooltip>
            </div>
            <div className="codes-panel codes-panel--modal">
              {codes.map((c, i) => (
                <div key={c} className="codes-panel__code">
                  <span className="codes-panel__index">{i + 1}</span>
                  {c}
                </div>
              ))}
            </div>
          </div>
        )}
      </Modal>

      <Drawer
        title="批次卡密详情"
        placement="right"
        width={420}
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        loading={detailLoading}
        extra={
          detail && detail.codes.length > 0 ? (
            <Button
              type="text"
              icon={<CopyOutlined />}
              onClick={() => copyCodes(detail.codes)}
            >
              复制
            </Button>
          ) : null
        }
      >
        {detail && (
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <div className="voucher-detail__meta">
              <div><Text type="secondary">批次名称</Text><div>{detail.batch.name}</div></div>
              <div><Text type="secondary">面额</Text><div>{formatTrafficMB(detail.batch.traffic_mb)}</div></div>
              <div><Text type="secondary">使用期间</Text><div>{detail.batch.valid_days} 天</div></div>
              <div><Text type="secondary">创建时间</Text><div>{new Date(detail.batch.created_at).toLocaleString('zh-CN')}</div></div>
            </div>

            <Divider style={{ margin: '8px 0' }} />

            {detail.codes.length > 0 ? (
              detail.codes.map((code, i) => {
                const voucher = detail.vouchers[i];
                const status = voucher ? VOUCHER_STATUS[voucher.status] : null;
                return (
                  <div key={code} className="voucher-detail__item">
                    <div className="codes-panel__code">{code}</div>
                    {status && <Tag color={status.color}>{status.label}</Tag>}
                  </div>
                );
              })
            ) : (
              <Text type="secondary">该批次未保存明文卡密（历史数据）</Text>
            )}
          </Space>
        )}
      </Drawer>
    </PageShell>
  );
}
