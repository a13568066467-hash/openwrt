import { useState } from 'react';
import { Toast } from 'antd-mobile';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { userApi, formatBytes } from '../api';
import { PageHero, PageLoading, SectionTitle, StepGuide } from '../components/PageShell';
import { RechargeTabIcon } from '../components/icons/TabBarIcons';

export default function RechargePage() {
  const qc = useQueryClient();
  const [code, setCode] = useState('');
  const [loading, setLoading] = useState(false);

  const { data: user, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: () => userApi.getProfile().then(r => r.data),
  });

  const handleRedeem = async () => {
    // 后端生成 16 位小写 hex；统一去掉空格/连字符并转小写，避免大小写导致校验失败
    const normalized = code.replace(/[\s-]/g, '').toLowerCase();
    if (!normalized) {
      Toast.show({ content: '请输入卡密' });
      return;
    }
    setLoading(true);
    try {
      const { data } = await userApi.redeemVoucher(normalized);
      Toast.show({ icon: 'success', content: `充值成功！余额 ${formatBytes(data.balance_bytes)}` });
      setCode('');
      qc.invalidateQueries({ queryKey: ['profile'] });
      qc.invalidateQueries({ queryKey: ['redeemed-vouchers'] });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: string } })?.response?.data;
      const text = typeof msg === 'string' ? msg : '';
      Toast.show({
        icon: 'fail',
        content: text.includes('already used') ? '卡密已被使用' : '卡密无效，请核对后重试',
      });
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) return <PageLoading />;

  return (
    <div className="page page--recharge">
      <PageHero
        variant="recharge"
        title="卡密充值"
        subtitle="输入卡密，流量即时到账"
        icon={<RechargeTabIcon size={40} color="#fff" />}
        extra={
          <div className="balance-pill">
            <span className="balance-pill__label">当前余额</span>
            <span className="balance-pill__value">{formatBytes(user?.quota_remaining_bytes ?? 0)}</span>
          </div>
        }
      />

      <div className="page-body">
        <div className="recharge-card">
          <SectionTitle>输入卡密</SectionTitle>
          <p className="recharge-card__hint">每个卡密仅可使用一次，请核对后提交</p>

          <div className="voucher-input-wrap">
            <input
              className="voucher-input"
              value={code}
              onChange={e => setCode(e.target.value.replace(/[^0-9a-fA-F\s-]/g, '').toLowerCase())}
              placeholder="粘贴 16 位卡密"
              maxLength={32}
              autoComplete="off"
              spellCheck={false}
            />
            <div className="voucher-input__glow" aria-hidden />
          </div>

          <button
            type="button"
            className="btn-gradient"
            disabled={loading || !code.trim()}
            onClick={handleRedeem}
          >
            {loading ? '充值中…' : '立即充值'}
          </button>
        </div>

        <div className="surface-card surface-card--soft">
          <SectionTitle>充值流程</SectionTitle>
          <StepGuide
            steps={[
              { num: '1', title: '购买卡密', desc: '在套餐页选择方案并获取卡密' },
              { num: '2', title: '输入兑换', desc: '将卡密粘贴到上方输入框' },
              { num: '3', title: '即刻上网', desc: '流量到账后即可连接 WiFi 使用' },
            ]}
          />
        </div>
      </div>
    </div>
  );
}
