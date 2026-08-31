import { Table, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { adminApi } from '../api';
import PageShell from '../components/PageShell';

const ACTION_LABELS: Record<string, string> = {
  adjust_quota: '调整流量',
  update_branding: '更新品牌配置',
  kick_user: '踢用户下线',
};

const TARGET_LABELS: Record<string, string> = {
  user: '用户',
  setting: '系统设置',
};

export default function AuditPage() {
  const { data, isLoading } = useQuery({
    queryKey: ['audit'],
    queryFn: () => adminApi.getAuditLogs().then(r => r.data),
  });

  return (
    <PageShell title="审计日志">
      <Table
        loading={isLoading}
        dataSource={data}
        rowKey="id"
        pagination={{ pageSize: 10 }}
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          {
            title: '操作',
            dataIndex: 'action',
            render: (v: string) => (
              <Tag>{ACTION_LABELS[v] ?? v}</Tag>
            ),
          },
          {
            title: '目标类型',
            dataIndex: 'target_type',
            render: (v: string) => TARGET_LABELS[v] ?? v,
          },
          { title: '目标ID', dataIndex: 'target_id' },
          { title: '详情', dataIndex: 'detail', ellipsis: true },
          { title: '时间', dataIndex: 'created_at' },
        ]}
      />
    </PageShell>
  );
}
